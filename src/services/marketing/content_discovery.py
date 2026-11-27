# src/services/marketing/content_discovery.py
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse, urlunparse

import httpx

from src.config import settings
from src.security.ai_guardrails import inspect_and_wrap_input
from src.services.ai.engine import ai_engine
from src.services.marketing.strategy import (
    MAX_QUERIES_PER_RUN,
    MAX_RESULTS_PER_QUERY,
    build_content_curation_prompt,
    build_fallback_candidate_texts,
    build_keyword_generation_prompt,
)

logger = logging.getLogger("ContentDiscoveryService")

TAVILY_API_ENDPOINT = "https://api.tavily.com/search"
BRAVE_API_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
HTTP_TIMEOUT_SECONDS = 10.0

_WRAPPER_OPEN = "<untrusted_user_input>"
_WRAPPER_CLOSE = "</untrusted_user_input>"


@dataclass(frozen=True)
class BrandDNA:
    """Structured representation of a tenant's brand identity and content boundaries."""

    business_name: str
    business_type: str = "General"
    brand_style: str = ""
    anti_positioning: str = ""
    content_pillars: list[str] = field(default_factory=list)
    products_services: str = ""
    ai_tone: str = "Professional"


@dataclass(frozen=True)
class SearchHit:
    """Normalized, sanitized web search result returned by a managed Search API."""

    title: str
    url: str
    url_hash: str
    snippet: str
    query: str
    source_provider: str


@dataclass(frozen=True)
class ContentCandidate:
    """Vetted content idea awaiting business-owner approval before RAG ingestion."""

    title: str
    url: str
    url_hash: str
    summary_he: str
    draft_post_he: str
    relevance_reason: str
    matched_keyword: str
    source_provider: str


class SearchProvider(Protocol):
    """Protocol for managed web search providers."""

    provider_name: str

    async def search(
        self, query: str, max_results: int = MAX_RESULTS_PER_QUERY
    ) -> list[SearchHit]: ...


def sanitize_untrusted_text(raw_text: str, max_len: int = 500) -> str:
    """Sanitizes untrusted external or user text to mitigate indirect prompt injection."""
    cleaned = inspect_and_wrap_input((raw_text or "").strip()).clean_text.strip()
    # Remove only the single outermost guardrail wrapper while still escaping any inner tags
    cleaned = cleaned.removeprefix(_WRAPPER_OPEN)
    cleaned = cleaned.removesuffix(_WRAPPER_CLOSE)
    cleaned = cleaned.replace("<", "&lt;").replace(">", "&gt;")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def normalize_and_hash_url(raw_url: str) -> tuple[str, str] | None:
    """
    Validates that a URL uses an allowed public web scheme (http/https),
    normalizes fragments and trailing slashes, and returns (normalized_url, sha256_hash).
    """
    if not raw_url or not isinstance(raw_url, str):
        return None
    try:
        parsed = urlparse(raw_url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    normalized_path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            parsed.query,
            "",
        )
    )
    url_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return normalized, url_hash


def _extract_json_payload(raw_text: str) -> Any:
    """Extracts JSON object or array from LLM output, stripping optional Markdown fences."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _extract_ai_text(ai_result: Any) -> str:
    """Normalizes ai_engine.generate_raw_analysis output into a plain string."""
    if isinstance(ai_result, dict):
        return str(ai_result.get("reply_text") or ai_result.get("summary") or "")
    if isinstance(ai_result, str):
        return ai_result
    return ""


class TavilySearchProvider:
    """Managed web search client backed by Tavily Search API (zero arbitrary URL fetching)."""

    provider_name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[SearchHit]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_raw_content": False,
        }
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            resp = await client.post(TAVILY_API_ENDPOINT, json=payload)
            resp.raise_for_status()
            data = resp.json()

        hits: list[SearchHit] = []
        for item in data.get("results", []):
            norm = normalize_and_hash_url(item.get("url", ""))
            if not norm:
                continue
            normalized_url, url_hash = norm
            title = sanitize_untrusted_text(item.get("title", ""), max_len=180)
            snippet = sanitize_untrusted_text(item.get("content", ""), max_len=500)
            if not title and not snippet:
                continue
            hits.append(
                SearchHit(
                    title=title,
                    url=normalized_url,
                    url_hash=url_hash,
                    snippet=snippet,
                    query=query,
                    source_provider=self.provider_name,
                )
            )
        return hits


class BraveSearchProvider:
    """Managed web search client backed by Brave Search API (zero arbitrary URL fetching)."""

    provider_name = "brave"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[SearchHit]:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        params = {"q": query, "count": max_results}
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            resp = await client.get(BRAVE_API_ENDPOINT, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        hits: list[SearchHit] = []
        for item in data.get("web", {}).get("results", []):
            norm = normalize_and_hash_url(item.get("url", ""))
            if not norm:
                continue
            normalized_url, url_hash = norm
            title = sanitize_untrusted_text(item.get("title", ""), max_len=180)
            snippet = sanitize_untrusted_text(item.get("description", ""), max_len=500)
            if not title and not snippet:
                continue
            hits.append(
                SearchHit(
                    title=title,
                    url=normalized_url,
                    url_hash=url_hash,
                    snippet=snippet,
                    query=query,
                    source_provider=self.provider_name,
                )
            )
        return hits


class NullSearchProvider:
    """Safe no-op search provider used when no external Search API key is configured."""

    provider_name = "disabled"

    async def search(self, query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[SearchHit]:
        logger.warning("Content discovery skipped: no TAVILY_API_KEY or BRAVE_SEARCH_API_KEY set.")
        return []


def get_search_provider() -> SearchProvider:
    """Resolves the configured Search API provider based on environment settings."""
    tavily_key = getattr(settings, "TAVILY_API_KEY", "") or os.getenv("TAVILY_API_KEY", "")
    if tavily_key and not tavily_key.startswith("dummy"):
        return TavilySearchProvider(api_key=tavily_key)

    brave_key = getattr(settings, "BRAVE_SEARCH_API_KEY", "") or os.getenv(
        "BRAVE_SEARCH_API_KEY", ""
    )
    if brave_key and not brave_key.startswith("dummy"):
        return BraveSearchProvider(api_key=brave_key)

    return NullSearchProvider()


def generate_search_keywords(brand: BrandDNA, max_keywords: int = 6) -> list[str]:
    """
    Generates targeted Hebrew and English search keywords from a tenant's Brand DNA,
    respecting their style and anti-positioning constraints.
    """
    pillars_text = ", ".join(
        sanitize_untrusted_text(p, max_len=80) for p in brand.content_pillars if p
    )
    prompt = build_keyword_generation_prompt(
        business_name=sanitize_untrusted_text(brand.business_name, 120),
        business_type=sanitize_untrusted_text(brand.business_type, 80),
        brand_style=sanitize_untrusted_text(brand.brand_style, 300),
        anti_positioning=sanitize_untrusted_text(brand.anti_positioning, 300),
        pillars_text=pillars_text,
        products_services=sanitize_untrusted_text(brand.products_services, 500),
        max_keywords=max_keywords,
    )

    try:
        raw_text = _extract_ai_text(ai_engine.generate_raw_analysis(prompt=prompt))
        parsed = _extract_json_payload(raw_text)
        if isinstance(parsed, list):
            cleaned = [
                sanitize_untrusted_text(str(item), max_len=120)
                for item in parsed
                if isinstance(item, str) and len(item.strip()) >= 3
            ]
            # Preserve order while removing duplicates
            deduped = list(dict.fromkeys(cleaned))
            if deduped:
                return deduped[:max_keywords]
    except Exception as exc:
        logger.warning("LLM keyword generation failed; using deterministic fallback: %s", exc)

    # Deterministic fallback built directly from Brand DNA fields
    fallback: list[str] = []
    for pillar in brand.content_pillars:
        clean_pillar = sanitize_untrusted_text(pillar, max_len=80)
        if clean_pillar:
            fallback.append(clean_pillar)
    if brand.brand_style:
        fallback.append(sanitize_untrusted_text(brand.brand_style, max_len=80))
    if brand.business_type and brand.business_type.lower() != "general":
        fallback.append(f"{sanitize_untrusted_text(brand.business_type, 60)} tips trends")
    return list(dict.fromkeys(fallback))[:max_keywords]


async def discover_content_candidates(
    brand: BrandDNA,
    keywords: list[str],
    existing_url_hashes: set[str] | None = None,
    provider: SearchProvider | None = None,
    max_queries: int = MAX_QUERIES_PER_RUN,
    max_results_per_query: int = MAX_RESULTS_PER_QUERY,
    max_candidates: int = 3,
) -> list[ContentCandidate]:
    """
    Executes capped web searches for a tenant's keywords, deduplicates results by url_hash,
    filters against anti-positioning, and drafts Hebrew approval previews and Instagram post ideas.
    """
    active_provider = provider or get_search_provider()
    seen_hashes: set[str] = set(existing_url_hashes or set())
    capped_keywords = [
        sanitize_untrusted_text(k, max_len=120) for k in keywords if k and len(k.strip()) >= 2
    ][:max_queries]

    if not capped_keywords:
        return []

    hits_by_hash: dict[str, SearchHit] = {}
    for kw in capped_keywords:
        try:
            results = await active_provider.search(kw, max_results=max_results_per_query)
        except Exception as exc:
            logger.warning(
                "Search provider '%s' failed for query '%s': %s",
                active_provider.provider_name,
                kw,
                exc,
            )
            continue

        for hit in results:
            if hit.url_hash in seen_hashes or hit.url_hash in hits_by_hash:
                continue
            hits_by_hash[hit.url_hash] = hit

    if not hits_by_hash:
        return []

    serialized_hits = [
        {
            "url_hash": h.url_hash,
            "matched_keyword": h.query,
            "title": h.title,
            "snippet": h.snippet,
        }
        for h in hits_by_hash.values()
    ]

    prompt = build_content_curation_prompt(
        business_name=sanitize_untrusted_text(brand.business_name, 120),
        business_type=sanitize_untrusted_text(brand.business_type, 80),
        brand_style=sanitize_untrusted_text(brand.brand_style, 300),
        anti_positioning=sanitize_untrusted_text(brand.anti_positioning, 300),
        ai_tone=sanitize_untrusted_text(brand.ai_tone, 60),
        serialized_hits=serialized_hits,
        max_candidates=max_candidates,
    )

    candidates: list[ContentCandidate] = []
    try:
        raw_text = _extract_ai_text(ai_engine.generate_raw_analysis(prompt=prompt))
        parsed = _extract_json_payload(raw_text)
        if isinstance(parsed, list):
            for entry in parsed:
                if not isinstance(entry, dict):
                    continue
                url_hash = str(entry.get("url_hash", ""))
                # Strictly enforce grounding: discard any hallucinated or unknown url_hash
                matched_hit = hits_by_hash.get(url_hash)
                if not matched_hit:
                    continue
                summary_he = sanitize_untrusted_text(str(entry.get("summary_he", "")), max_len=400)
                draft_post_he = sanitize_untrusted_text(
                    str(entry.get("draft_post_he", "")), max_len=1200
                )
                reason = sanitize_untrusted_text(
                    str(entry.get("relevance_reason", "")), max_len=250
                )
                if not summary_he or not draft_post_he:
                    continue
                candidates.append(
                    ContentCandidate(
                        title=matched_hit.title,
                        url=matched_hit.url,
                        url_hash=matched_hit.url_hash,
                        summary_he=summary_he,
                        draft_post_he=draft_post_he,
                        relevance_reason=reason,
                        matched_keyword=matched_hit.query,
                        source_provider=matched_hit.source_provider,
                    )
                )
                if len(candidates) >= max_candidates:
                    break
    except Exception as exc:
        logger.warning("LLM curation failed; falling back to sanitized top search hits: %s", exc)

    if not candidates:
        for hit in list(hits_by_hash.values())[:max_candidates]:
            summary_he, draft_post_he, relevance_reason = build_fallback_candidate_texts(
                query=hit.query, title=hit.title, snippet=hit.snippet
            )
            candidates.append(
                ContentCandidate(
                    title=hit.title,
                    url=hit.url,
                    url_hash=hit.url_hash,
                    summary_he=summary_he,
                    draft_post_he=draft_post_he,
                    relevance_reason=relevance_reason,
                    matched_keyword=hit.query,
                    source_provider=hit.source_provider,
                )
            )

    return candidates
