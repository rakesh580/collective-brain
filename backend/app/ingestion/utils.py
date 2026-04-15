"""Shared utilities for ingestion connectors."""

import hashlib
import re


def content_hash(text: str) -> str:
    """SHA-256 hex digest of normalised text — used for deduplication on re-sync."""
    normalised = " ".join(text.split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def extract_topics_from_text(text: str, max_topics: int = 10) -> list[str]:
    """Heuristic keyword extraction: title-case words and tech nouns."""
    # Keep words ≥5 chars that start with uppercase or are known tech terms
    tech_pattern = re.compile(
        r"\b(API|SDK|backend|frontend|database|auth|deploy|docker|python|"
        r"react|sql|graphql|rest|grpc|kubernetes|aws|gcp|azure|"
        r"postgresql|postgres|redis|kafka|llm|embedding|vector|rag)\b",
        re.IGNORECASE,
    )
    topics: list[str] = []
    for match in tech_pattern.finditer(text):
        t = match.group(0).lower()
        if t not in topics:
            topics.append(t)
    return topics[:max_topics]


def slugify(text: str, max_length: int = 50) -> str:
    """URL-safe slug from arbitrary text."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length]
