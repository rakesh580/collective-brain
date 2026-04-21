"""Unit tests for app.ingestion.topic_extractor.

These guard the canonical allowlist: any change that lets sentence
fragments leak into topics should break one of these tests.
"""

from app.ingestion.topic_extractor import (
    CANONICAL_TOPICS,
    canonicalize,
    canonicalize_list,
    extract_topics_from_commit,
    extract_topics_from_labels,
)


class TestCanonicalize:
    def test_accepts_canonical_topic(self):
        assert canonicalize("python") == "python"
        assert canonicalize("frontend") == "frontend"

    def test_maps_alias_to_canonical(self):
        assert canonicalize("ts") == "typescript"
        assert canonicalize("js") == "javascript"
        assert canonicalize("k8s") == "kubernetes"
        assert canonicalize("pg") == "postgresql"
        assert canonicalize("hf") == "huggingface"

    def test_rejects_unknown(self):
        assert canonicalize("foobar") is None
        assert canonicalize(": declutter network graph — zoom-aware labels") is None
        assert canonicalize("some-random-commit-body-text") is None

    def test_normalizes_case_and_edges(self):
        assert canonicalize("  Python ") == "python"
        assert canonicalize("-- TypeScript --") == "typescript"
        assert canonicalize(":python:") == "python"

    def test_handles_none_and_empty(self):
        assert canonicalize(None) is None
        assert canonicalize("") is None
        assert canonicalize("   ") is None

    def test_prefix_aliases_canonicalize(self):
        assert canonicalize("fix") == "bugfix"
        assert canonicalize("feat") == "feature"
        assert canonicalize("ci") == "ci-cd"
        assert canonicalize("cd") == "ci-cd"


class TestCanonicalizeList:
    def test_filters_noise_out(self):
        polluted = [
            "python",
            ": test fixtures for ci — seed data, fk constraints",
            "ts build: remove unused login import",
            "frontend",
            "huggingface build",
            "chromadb internalerror",
        ]
        result = canonicalize_list(polluted)
        assert "python" in result
        assert "frontend" in result
        # The long sentence fragments and multi-word phrases are rejected
        assert not any(len(r) > 30 for r in result)
        assert not any(" " in r for r in result)

    def test_maps_aliases_and_dedupes(self):
        result = canonicalize_list(["ts", "typescript", "TS"])
        assert result == ["typescript"]

    def test_sorted_output_is_stable(self):
        result = canonicalize_list(["python", "javascript", "react"])
        assert result == sorted(result)

    def test_handles_none_and_empty(self):
        assert canonicalize_list(None) == []
        assert canonicalize_list([]) == []
        assert canonicalize_list([""]) == []

    def test_respects_max_topics_cap(self):
        many = [
            "python",
            "javascript",
            "typescript",
            "react",
            "rust",
            "golang",
            "docker",
            "kubernetes",
            "aws",
            "postgresql",
            "frontend",
            "backend",
            "testing",
            "ci-cd",
        ]
        result = canonicalize_list(many, max_topics=5)
        assert len(result) == 5


class TestExtractTopicsFromCommit:
    def test_conventional_prefix_maps_to_canonical(self):
        result = extract_topics_from_commit("fix: handle null auth token", [])
        assert "bugfix" in result

        result = extract_topics_from_commit("feat: add decision intelligence", [])
        assert "feature" in result

        result = extract_topics_from_commit("ci: pin ruff version", [])
        assert "ci-cd" in result

        result = extract_topics_from_commit("build: bump deps", [])
        assert "build-system" in result

    def test_scope_in_parens_adds_canonical_topic(self):
        result = extract_topics_from_commit("feat(auth): add Google OAuth", [])
        assert "feature" in result
        assert "authentication" in result

    def test_scope_not_in_allowlist_is_dropped(self):
        # "launchready" is gibberish → should NOT pollute topics
        result = extract_topics_from_commit("feat(launchready): full test coverage", [])
        assert "feature" in result
        assert "launchready" not in result

    def test_no_prefix_yields_only_file_topics(self):
        result = extract_topics_from_commit(
            "Update stuff",
            ["backend/app/routers/auth.py", "frontend/src/pages/LoginPage.tsx"],
        )
        # No prefix → no feature/bugfix
        assert "feature" not in result
        assert "bugfix" not in result
        # Files → language + domain topics
        assert "python" in result
        assert "react" in result
        assert "api" in result  # routers/ → api
        assert "frontend" in result  # frontend/ → frontend

    def test_file_extensions_map_to_languages(self):
        result = extract_topics_from_commit("chore: cleanup", ["scripts/deploy.sh", "infra/main.tf"])
        assert "shell" in result
        assert "terraform" in result
        assert "scripting" in result  # scripts/
        assert "infrastructure" in result  # infra/

    def test_rejects_long_noisy_commit_body(self):
        noisy = (
            "This is not a conventional commit and has a really long commit body "
            "that used to leak into topics as sentence fragments, which we no "
            "longer want showing up on the graph."
        )
        result = extract_topics_from_commit(noisy, [])
        # Nothing should match the allowlist here
        assert result == []

    def test_empty_inputs_give_empty_result(self):
        assert extract_topics_from_commit("", []) == []
        assert extract_topics_from_commit(None, None) == []
        assert extract_topics_from_commit("   ", []) == []

    def test_result_is_sorted_and_capped(self):
        result = extract_topics_from_commit(
            "feat(frontend): sweeping changes",
            [f"src/component_{i}.tsx" for i in range(20)] + ["backend/api/routes.py", "tests/unit/test_x.py"],
            max_topics=5,
        )
        assert len(result) <= 5
        assert result == sorted(result)

    def test_colon_only_message_no_prefix_rejected(self):
        # ": test fixtures for ci — seed data" starts with colon, no prefix
        result = extract_topics_from_commit(": test fixtures for ci — seed data", [])
        # No canonical prefix → no noise topic
        assert "test" not in result or canonicalize("test") == "testing"
        # The bogus "fixtures for ci" string should never appear
        assert "fixtures for ci" not in result


class TestExtractTopicsFromLabels:
    def test_canonicalizes_labels(self):
        result = extract_topics_from_labels(["bug", "python", "frontend"])
        assert "bugfix" in result
        assert "python" in result
        assert "frontend" in result

    def test_drops_unknown_labels(self):
        result = extract_topics_from_labels(["bug", "wontfix", "needs-triage"])
        # Only "bug" is canonicalizable
        assert result == ["bugfix"]

    def test_empty_labels(self):
        assert extract_topics_from_labels([]) == []
        assert extract_topics_from_labels(None) == []


class TestCanonicalTopicsIntegrity:
    def test_prefix_targets_are_all_canonical(self):
        """Every prefix map target must also be in the allowlist."""
        from app.ingestion.topic_extractor import PREFIX_MAP

        for _, topic in PREFIX_MAP.items():
            assert topic in CANONICAL_TOPICS, f"{topic} from PREFIX_MAP missing from allowlist"

    def test_ext_targets_are_all_canonical(self):
        from app.ingestion.topic_extractor import EXT_MAP

        for _, topic in EXT_MAP.items():
            assert topic in CANONICAL_TOPICS, f"{topic} from EXT_MAP missing from allowlist"

    def test_dir_targets_are_all_canonical(self):
        from app.ingestion.topic_extractor import DIR_MAP

        for _, topic in DIR_MAP.items():
            assert topic in CANONICAL_TOPICS, f"{topic} from DIR_MAP missing from allowlist"

    def test_alias_targets_are_all_canonical(self):
        from app.ingestion.topic_extractor import ALIASES

        for src, dst in ALIASES.items():
            assert dst in CANONICAL_TOPICS, f"alias {src}->{dst} target missing from allowlist"
