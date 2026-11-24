# src/services/ai/harness.py
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

from google import genai
from google.genai import types

from src.config import settings
from src.schemas.ai_response import WhatsAppAgentResponse
from src.security.ai_guardrails import inspect_and_wrap_input, validate_llm_output
from src.services.ai.output_sanitizer import sanitize_ai_output
from src.services.ai.prompt_builder import PromptBuilder
from src.services.llm_router import GeminiTieredRouter, TaskComplexity

logger = logging.getLogger("AIHarness")

_FORBIDDEN_MARKERS = [
    "system instruction",
    "base_guardrails",
    "developer mode",
    "הוראות מערכת",
    "prompt",
]


@dataclass
class AgentRunMetrics:
    model_tier: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    tool_calls_count: int
    tool_names: list[str]
    context_compacted: bool


class AgentHarness:
    """
    Unified AI Harness for LeadFlow AI.
    Integrates Pre-LLM Guardrails, GeminiTieredRouter, Turn-1 Response Caching,
    Structured Pydantic Outputs (WhatsAppAgentResponse), and Post-LLM Validation.
    """

    def __init__(self) -> None:
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
            http_options=types.HttpOptions(timeout=15000),
        )
        redis_client = None
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            pass

        self.router = GeminiTieredRouter(gemini_client=client, redis_client=redis_client)

    async def execute_turn(
        self,
        tenant_id: str,
        business_type: str,
        business_name: str,
        products_services: str | None,
        custom_instructions: str | None,
        lead_name: str | None,
        lead_source: str,
        conversation_history: list[dict[str, Any]],
        latest_message: str,
        kb_version: int = 1,
        complexity: TaskComplexity = TaskComplexity.STANDARD,
        db: Any | None = None,
        lead_id: Any | None = None,
    ) -> dict[str, Any]:
        """
        Executes a complete AI turn with full security guardrails, caching, routing,
        and tenant-scoped tools.
        """
        start_time = time.perf_counter()
        sanitized = inspect_and_wrap_input(latest_message)
        if sanitized.is_flagged:
            logger.warning(
                f"Pre-LLM guardrail flagged input for tenant {tenant_id}: {sanitized.risk_reason}"
            )
            # In src/services/ai/harness.py, inside the pre-LLM (and post-LLM) guardrail return block:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "intent": "complaint",
                "reply_text": "אני מעביר את השיחה לנציג אנושי שיחזור אליך בהקדם.",
                "needs_human_escalation": True,
                "abstained": True,
                "metrics": {
                    "latency_ms": round(elapsed_ms, 2),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "model_used": "guardrail_blocked",
                    "cache_hit": False,
                },
            }

        effective_text = sanitized.clean_text

        tools = []
        tool_names = []
        if db is not None and lead_id is not None:
            try:
                from src.services.ai.tools import build_tenant_tools

                tools, tool_names = build_tenant_tools(db, tenant_id, lead_id)
            except Exception as tool_err:
                logger.warning(
                    f"Failed to build tenant tools (proceeding without tools): {tool_err}"
                )

        system_instruction = PromptBuilder.build_system_instruction(
            business_type=business_type,
            business_name=business_name,
            products_services=products_services,
            custom_instructions=custom_instructions,
            enabled_tools=tool_names,
        )

        retrieved_chunks = []
        if db is not None:
            try:
                from src.services.rag.retriever import retrieve_relevant_chunks

                retrieved_chunks = await retrieve_relevant_chunks(
                    db, tenant_id, effective_text, top_k=4, min_score=0.25
                )
            except Exception as rag_err:
                logger.warning(f"Failed to retrieve tenant knowledge chunks: {rag_err}")

        lead_turn_prompt = PromptBuilder.build_lead_turn_prompt(
            lead_name=lead_name,
            lead_source=lead_source,
            conversation_history=conversation_history,
            latest_message=effective_text,
            conversation_summary=None,
            extracted_state=None,
            retrieved_chunks=retrieved_chunks,
        )

        # Disable caching if tools or retrieved RAG knowledge are active
        cache_key = None
        if (
            len(conversation_history) == 0
            and not tools
            and not retrieved_chunks
            and self.router.redis is not None
        ):
            try:
                sys_hash = hashlib.sha256(system_instruction.encode("utf-8")).hexdigest()
                norm_input = effective_text.strip().lower()
                raw_cache_input = f"{tenant_id}:{kb_version}:{sys_hash}:{norm_input}"
                cache_key = f"ai_cache:v2:{tenant_id}:{hashlib.sha256(raw_cache_input.encode('utf-8')).hexdigest()}"
                cached = await self.router.redis.get(cache_key)
                if cached:
                    logger.info(f"⚡ AI Cache Hit for tenant {tenant_id}")
                    return json.loads(cached)
            except Exception as cache_err:
                logger.warning(f"Cache read error: {cache_err}")

        formatted_history: list[types.Content] = []
        for msg in conversation_history:
            role = (
                "user"
                if msg.get("sender_type") == "user" or msg.get("sender") == "user"
                else "model"
            )
            content = str(msg.get("content", "") or msg.get("text", ""))[
                : PromptBuilder.MAX_INBOUND_MESSAGE_LENGTH
            ]
            formatted_history.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content)],
                )
            )

        formatted_history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=lead_turn_prompt)],
            )
        )

        start_time = time.time()

        try:
            # If cache hit happened earlier, record trace and return
            # We can track cache_hit accurately:
            # (handled inside cache check block)

            response = await self.router.route_and_generate(
                tenant_id=tenant_id,
                prompt=lead_turn_prompt,
                complexity=complexity,
                response_schema=WhatsAppAgentResponse,
                system_instruction=system_instruction,
                tools=tools if tools else None,
                chat_history=formatted_history,
            )
            latency_ms = (time.time() - start_time) * 1000

            response_text = ""
            if hasattr(response, "text") and response.text:
                response_text = response.text
            else:
                response_text = str(response)

            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = (
                    getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                )
                total_tokens = getattr(response.usage_metadata, "total_token_count", 0) or (
                    prompt_tokens + completion_tokens
                )

            if prompt_tokens == 0:
                prompt_tokens = max(len(lead_turn_prompt) // 4, 10)
            if completion_tokens == 0:
                completion_tokens = max(len(response_text) // 4, 10)
            if total_tokens == 0:
                total_tokens = prompt_tokens + completion_tokens

            primary_model, _ = self.router.select_models(complexity)
            input_rate = 0.075 / 1_000_000
            output_rate = 0.30 / 1_000_000
            est_cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
            context_compacted = len(conversation_history) > 8

            metrics = AgentRunMetrics(
                model_tier=primary_model,
                latency_ms=round(latency_ms, 2),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=round(est_cost, 7),
                tool_calls_count=len(tools),
                tool_names=tool_names,
                context_compacted=context_compacted,
            )

            parsed_data: dict[str, Any] = {}
            try:
                cleaned_json = response_text.strip()
                cleaned_json = cleaned_json.removeprefix("```json")
                cleaned_json = cleaned_json.removesuffix("```")
                parsed_data = json.loads(cleaned_json.strip())
            except Exception:
                parsed_data = {
                    "reply_text": sanitize_ai_output(response_text[:600]),
                    "lead_intent": "INQUIRY",
                    "lead_qualification_score": 50,
                    "needs_human_escalation": False,
                    "abstained": False,
                }

            raw_reply = parsed_data.get("reply_text", "")
            validated_reply = validate_llm_output(raw_reply, forbidden_markers=_FORBIDDEN_MARKERS)
            final_reply = sanitize_ai_output(validated_reply)

            upper_reply = final_reply.upper()
            needs_human = (
                bool(parsed_data.get("needs_human_escalation", False))
                or "[HANDOFF]" in upper_reply
                or "HANDOFF" in upper_reply
                or bool(parsed_data.get("abstained", False))
            )

            if self.router.redis is not None:
                try:
                    await self.router.redis.incr("llm:metrics:success")
                    await self.router.redis.expire("llm:metrics:success", 1800)
                    if needs_human:
                        await self.router.redis.incr("llm:metrics:escalated")
                        await self.router.redis.expire("llm:metrics:escalated", 1800)
                except Exception:
                    pass

            result = {
                "intent": parsed_data.get("lead_intent", "INQUIRY").lower(),
                "reply_text": final_reply.replace("[HANDOFF]", "").replace("[handoff]", "").strip(),
                "lead_qualification_score": int(parsed_data.get("lead_qualification_score", 50)),
                "needs_human_escalation": needs_human,
                "abstained": bool(parsed_data.get("abstained", False)),
                "cited_chunk_ids": parsed_data.get("cited_chunk_ids", []),
                "metrics": asdict(metrics),
            }

            if cache_key and self.router.redis is not None and not needs_human:
                try:
                    await self.router.redis.setex(cache_key, 86400, json.dumps(result))
                except Exception as cache_write_err:
                    logger.warning(f"Cache write error: {cache_write_err}")

            # Record PII-safe AI turn trace
            from src.services.ai.tracing import record_ai_turn_trace

            primary_model, _ = self.router.select_models(complexity)
            est_tokens = len(lead_turn_prompt) // 4
            record_ai_turn_trace(
                tenant_id=tenant_id,
                lead_id="lead_active",
                model_used=primary_model,
                complexity_tier=complexity.value,
                latency_ms=latency_ms,
                input_tokens=est_tokens,
                output_tokens=len(final_reply) // 4,
                cache_hit=False,
                abstained=result["abstained"],
                needs_human=needs_human,
            )

            return result

        except Exception as e:
            if self.router.redis is not None:
                try:
                    await self.router.redis.incr("llm:metrics:error")
                    await self.router.redis.expire("llm:metrics:error", 1800)
                except Exception:
                    pass
            logger.error(
                f"Agent Harness execution failed for tenant {tenant_id}: {type(e).__name__} - {e}"
            )
            return {
                "intent": "error",
                "reply_text": "אני קצת עמוסה כרגע, העברתי את פנייתך לצוות שיחזור אליך בהקדם.",
                "lead_qualification_score": 0,
                "needs_human_escalation": True,
                "abstained": True,
            }


# Singleton Harness Instance
agent_harness = AgentHarness()
