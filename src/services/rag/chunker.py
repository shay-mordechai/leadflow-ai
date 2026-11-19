# src/services/rag/chunker.py
import logging
import re
from typing import Any

logger = logging.getLogger("RAGChunker")


def extract_text_from_bytes(raw_bytes: bytes, content_type: str) -> str:
    """Extracts raw text from uploaded PDF, Markdown, or TXT bytes with graceful fallbacks."""
    text = ""
    ct = (content_type or "").lower()
    if "pdf" in ct or raw_bytes.startswith(b"%PDF"):
        try:
            import io

            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
            pages_text = []
            for page in reader.pages:
                pt = page.extract_text()
                if pt:
                    pages_text.append(pt)
            text = "\n".join(pages_text)
        except Exception as pdf_err:
            logger.warning(f"pypdf extraction failed, falling back to decode: {pdf_err}")
            text = raw_bytes.decode("utf-8", errors="ignore")
    else:
        text = raw_bytes.decode("utf-8", errors="ignore")
    return text


def chunk_document_text(
    text: str, max_chars: int = 1400, overlap: int = 200
) -> list[dict[str, Any]]:
    """
    Structure-aware chunking for text/markdown documents.
    Splits by headings while keeping pricing rows and paragraphs intact.
    Returns a list of dicts with 'section_title' and 'content'.
    """
    if not text.strip():
        return []

    # Split by markdown headers (#, ##, ###) or double newlines
    section_pattern = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)
    splits = section_pattern.split(text)

    sections = []
    current_title = "General"
    current_body = []

    for part in splits:
        if section_pattern.match(part.strip()):
            if current_body:
                sections.append(
                    {"section_title": current_title, "content": "\n".join(current_body).strip()}
                )
                current_body = []
            current_title = part.strip().lstrip("#").strip()
        else:
            if part.strip():
                current_body.append(part)

    if current_body:
        sections.append(
            {"section_title": current_title, "content": "\n".join(current_body).strip()}
        )

    chunks = []
    chunk_index = 0

    for section in sections:
        sec_title = section["section_title"]
        sec_content = section["content"]

        # If section is small enough, keep as single chunk
        if len(sec_content) <= max_chars:
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "section_title": sec_title,
                    "content": sec_content,
                }
            )
            chunk_index += 1
        else:
            # Sliding window chunking within section
            start = 0
            while start < len(sec_content):
                end = start + max_chars
                chunk_text = sec_content[start:end]
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "section_title": sec_title,
                        "content": chunk_text.strip(),
                    }
                )
                chunk_index += 1
                start += max_chars - overlap

    return chunks
