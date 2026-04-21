"""Canonical topic extraction for commits, PRs, and other content sources.

Topics power the knowledge graph, trending topics, expertise tags, and
expert routing. Free-text extraction from commit subjects pollutes these
surfaces with sentence fragments, so extraction is strictly rule-based:
a topic is only produced if it matches an entry in CANONICAL_TOPICS
(directly or via an alias).

Call sites:
- app.ingestion.git_connector.GitConnector.parse
- app.services.github_event_processor.GitHubEventProcessor.process_push / _pr
- scripts/backfill_topics.py (via canonicalize_list)
"""

from __future__ import annotations

import re

# Conventional-commit prefixes → canonical topic
PREFIX_MAP: dict[str, str] = {
    "feat": "feature",
    "feature": "feature",
    "fix": "bugfix",
    "hotfix": "bugfix",
    "bug": "bugfix",
    "refactor": "refactoring",
    "docs": "documentation",
    "doc": "documentation",
    "test": "testing",
    "tests": "testing",
    "chore": "maintenance",
    "ci": "ci-cd",
    "cd": "ci-cd",
    "perf": "performance",
    "style": "code-style",
    "build": "build-system",
    "revert": "maintenance",
    "security": "security",
    "deps": "maintenance",
}

# File extension → canonical topic
EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "react",
    ".ts": "typescript",
    ".tsx": "react",
    ".go": "golang",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "database",
    ".yml": "config",
    ".yaml": "config",
    ".toml": "config",
    ".json": "config",
    ".html": "frontend",
    ".css": "frontend",
    ".scss": "frontend",
    ".sass": "frontend",
    ".vue": "vue",
    ".svelte": "svelte",
    ".tf": "terraform",
    ".dockerfile": "docker",
    ".md": "documentation",
    ".rst": "documentation",
}

# Directory name → canonical topic
DIR_MAP: dict[str, str] = {
    "api": "api",
    "apis": "api",
    "routers": "api",
    "routes": "api",
    "controllers": "api",
    "endpoints": "api",
    "auth": "authentication",
    "authentication": "authentication",
    "oauth": "authentication",
    "sso": "authentication",
    "test": "testing",
    "tests": "testing",
    "__tests__": "testing",
    "spec": "testing",
    "specs": "testing",
    "deploy": "deployment",
    "deployment": "deployment",
    "deployments": "deployment",
    "infra": "infrastructure",
    "infrastructure": "infrastructure",
    "docs": "documentation",
    "doc": "documentation",
    "documentation": "documentation",
    "frontend": "frontend",
    "ui": "frontend",
    "client": "frontend",
    "web": "frontend",
    "components": "frontend",
    "pages": "frontend",
    "hooks": "frontend",
    "backend": "backend",
    "server": "backend",
    "services": "backend",
    "middleware": "backend",
    "models": "data-models",
    "schemas": "data-models",
    "migrations": "database",
    "alembic": "database",
    "scripts": "scripting",
    "observability": "observability",
    "monitoring": "observability",
    "logging": "observability",
    "security": "security",
    ".github": "github",
    "workflows": "ci-cd",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "docker": "docker",
    "nginx": "infrastructure",
    "terraform": "terraform",
    ".claude": "claude-code",
    "ingestion": "ingestion",
    "memory_graph": "knowledge-graph",
    "rag_pipeline": "rag",
    "rag": "rag",
    "vector_store": "vector-search",
    "llm": "llm",
    "embedding": "embeddings",
    "embeddings": "embeddings",
}

# Aliases → canonical. Covers common shortenings and older topic forms
# that may already be in the database.
ALIASES: dict[str, str] = {
    "ts": "typescript",
    "js": "javascript",
    "py": "python",
    "rb": "ruby",
    "fe": "frontend",
    "be": "backend",
    "postgres": "postgresql",
    "pg": "postgresql",
    "k8s": "kubernetes",
    "k3s": "kubernetes",
    "auth": "authentication",
    "oauth": "authentication",
    "hf": "huggingface",
    "hf-spaces": "huggingface-spaces",
    "huggingface-space": "huggingface-spaces",
    "tests": "testing",
    "test": "testing",
    "docs": "documentation",
    "doc": "documentation",
    "fix": "bugfix",
    "bug": "bugfix",
    "hotfix": "bugfix",
    "feat": "feature",
    "chore": "maintenance",
    "perf": "performance",
    "refactor": "refactoring",
    "ci": "ci-cd",
    "cd": "ci-cd",
    "build": "build-system",
    "deploy": "deployment",
    ".github": "github",
    "gh": "github",
    "ghactions": "ci-cd",
    "github-actions": "ci-cd",
    "chroma": "chromadb",
    "vector-db": "vector-search",
    "vectordb": "vector-search",
    "ml": "machine-learning",
    "nlp": "machine-learning",
}

# Canonical allowlist. Anything not in here (directly or via aliases)
# is rejected. Keep this list tight — every entry should be a topic a
# user would recognize at a glance on the graph / trending panel.
CANONICAL_TOPICS: frozenset[str] = frozenset(
    {
        # Languages
        "python",
        "javascript",
        "typescript",
        "react",
        "vue",
        "svelte",
        "golang",
        "rust",
        "java",
        "kotlin",
        "ruby",
        "php",
        "swift",
        "csharp",
        "cpp",
        "c",
        "shell",
        "html",
        "css",
        # Data / databases
        "postgresql",
        "mysql",
        "sqlite",
        "mongodb",
        "redis",
        "chromadb",
        "pgvector",
        "supabase",
        "database",
        "sql",
        "vector-search",
        "embeddings",
        # Infra / cloud
        "docker",
        "kubernetes",
        "terraform",
        "aws",
        "gcp",
        "azure",
        "nginx",
        "infrastructure",
        # CI / dev tooling
        "ci-cd",
        "github",
        "gitlab",
        "deployment",
        "build-system",
        "huggingface",
        "huggingface-spaces",
        "claude-code",
        # Domains
        "frontend",
        "backend",
        "api",
        "authentication",
        "testing",
        "security",
        "observability",
        "scripting",
        "data-models",
        "documentation",
        "rag",
        "llm",
        "knowledge-graph",
        "ingestion",
        "machine-learning",
        # Work types
        "feature",
        "bugfix",
        "refactoring",
        "maintenance",
        "performance",
        "code-style",
        # Config
        "config",
    }
)

# Extract `prefix(scope):` up to the colon
_PREFIX_RE = re.compile(
    r"^\s*([a-zA-Z]+)(?:\(([^)]{1,60})\))?!?\s*:\s*",
    re.IGNORECASE,
)

_SCOPE_SPLIT_RE = re.compile(r"[,/\s]+")
_CLEAN_EDGES_RE = re.compile(r"^[-:_\s.]+|[-:_\s.]+$")


def canonicalize(raw: str | None) -> str | None:
    """Normalize a single topic string to its canonical form.

    Returns None if the input doesn't match any known topic. Safe for
    any input (commit subjects, labels, old DB rows).
    """
    if not raw:
        return None
    token = _CLEAN_EDGES_RE.sub("", str(raw).strip().lower())
    if not token:
        return None
    # Aliases first — they may remap shortened forms to canonical
    token = ALIASES.get(token, token)
    if token in CANONICAL_TOPICS:
        return token
    return None


def canonicalize_list(raw_topics: list[str] | None, max_topics: int = 12) -> list[str]:
    """Filter and normalize a list of raw topic strings.

    Drops anything not on the allowlist. Deduplicates. Sorted for
    stable output (makes backfills idempotent and diffs reviewable).
    """
    out: set[str] = set()
    for raw in raw_topics or []:
        canonical = canonicalize(raw)
        if canonical:
            out.add(canonical)
    return sorted(out)[:max_topics]


def _extract_prefix_topics(message: str) -> set[str]:
    """Pull conventional-commit prefix + scope from a commit subject."""
    if not message:
        return set()
    first_line = message.split("\n", 1)[0]
    match = _PREFIX_RE.match(first_line)
    if not match:
        return set()

    topics: set[str] = set()
    prefix = (match.group(1) or "").lower()
    if prefix in PREFIX_MAP:
        topics.add(PREFIX_MAP[prefix])

    scope_raw = match.group(2) or ""
    if scope_raw:
        for piece in _SCOPE_SPLIT_RE.split(scope_raw):
            canonical = canonicalize(piece)
            if canonical:
                topics.add(canonical)
    return topics


def _extract_file_topics(files: list[str]) -> set[str]:
    """Pull language + directory topics from a list of changed file paths."""
    topics: set[str] = set()
    for f in files[:40]:  # cap to bound work on large PRs
        if not f:
            continue
        path = f.lower()
        parts = [p for p in path.split("/") if p]
        # Directory topics (allowlist lookup)
        for part in parts[:-1]:
            mapped = DIR_MAP.get(part)
            if mapped:
                topics.add(mapped)
        # Extension → language topic
        leaf = parts[-1] if parts else ""
        if "." in leaf:
            ext = "." + leaf.rsplit(".", 1)[-1]
            mapped_ext = EXT_MAP.get(ext)
            if mapped_ext:
                topics.add(mapped_ext)
    return topics


def extract_topics_from_commit(
    message: str | None,
    files: list[str] | None = None,
    max_topics: int = 10,
) -> list[str]:
    """Canonical topics for a commit / PR title + changed-files list.

    Strictly rule-based: only returns topics on the allowlist. Safe to
    call on any string without producing noise.
    """
    topics: set[str] = set()
    topics |= _extract_prefix_topics(message or "")
    topics |= _extract_file_topics(files or [])
    return sorted(topics)[:max_topics]


def extract_topics_from_labels(
    labels: list[str] | None,
    max_topics: int = 10,
) -> list[str]:
    """Canonical topics from GitHub / issue labels.

    Useful for PR/issue events where labels carry human intent.
    """
    return canonicalize_list(labels, max_topics=max_topics)
