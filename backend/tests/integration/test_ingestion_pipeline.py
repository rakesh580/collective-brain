"""Integration tests for data ingestion endpoints."""

import io
import json
import zipfile


class TestMarkdownUpload:
    def test_upload_single_markdown(self, app_client, auth_headers):
        content = b"# Test Doc\n\nSome knowledge content here."
        files = [("files", ("test.md", io.BytesIO(content), "text/markdown"))]
        resp = app_client.post("/ingest/markdown-upload", headers=auth_headers, files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_count"] >= 1

    def test_upload_multiple_files(self, app_client, auth_headers):
        files = [
            ("files", ("a.md", io.BytesIO(b"# File A\nContent A"), "text/markdown")),
            ("files", ("b.md", io.BytesIO(b"# File B\nContent B"), "text/markdown")),
        ]
        resp = app_client.post("/ingest/markdown-upload", headers=auth_headers, files=files)
        assert resp.status_code == 200
        assert resp.json()["chunk_count"] >= 2

    def test_upload_requires_auth(self, app_client):
        files = [("files", ("test.md", io.BytesIO(b"# Hello"), "text/markdown"))]
        resp = app_client.post("/ingest/markdown-upload", files=files)
        assert resp.status_code == 401

    def test_upload_oversized_file_rejected(self, app_client, auth_headers):
        """Files over 50 MB should be rejected with 413."""
        big = b"x" * (50 * 1024 * 1024 + 1)
        files = [("files", ("big.md", io.BytesIO(big), "text/markdown"))]
        resp = app_client.post("/ingest/markdown-upload", headers=auth_headers, files=files)
        assert resp.status_code == 413


class TestDocumentUpload:
    def test_upload_txt_file(self, app_client, auth_headers):
        content = b"Plain text knowledge document with useful information."
        files = [("files", ("doc.txt", io.BytesIO(content), "text/plain"))]
        resp = app_client.post("/ingest/documents", headers=auth_headers, files=files)
        assert resp.status_code == 200

    def test_upload_unsupported_extension(self, app_client, auth_headers):
        files = [("files", ("bad.exe", io.BytesIO(b"binary"), "application/octet-stream"))]
        resp = app_client.post("/ingest/documents", headers=auth_headers, files=files)
        # Should either reject or ignore unsupported types
        assert resp.status_code in (200, 400, 422)


class TestSlackIngestion:
    def test_ingest_slack_zip(self, app_client, auth_headers):
        """Create a minimal Slack export ZIP and ingest it."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            channel_data = [
                {
                    "user": "U123",
                    "text": "Hello from Slack!",
                    "ts": "1700000000.000001",
                    "user_profile": {"real_name": "Alice"},
                }
            ]
            zf.writestr("general/2024-01-01.json", json.dumps(channel_data))
        buf.seek(0)
        files = [("file", ("slack_export.zip", buf, "application/zip"))]
        resp = app_client.post("/ingest/slack", headers=auth_headers, files=files)
        assert resp.status_code == 200

    def test_ingest_slack_requires_auth(self, app_client):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("general/2024-01-01.json", "[]")
        buf.seek(0)
        resp = app_client.post("/ingest/slack", files=[("file", ("e.zip", buf, "application/zip"))])
        assert resp.status_code == 401


class TestDiscordIngestion:
    def test_ingest_discord_json(self, app_client, auth_headers):
        data = {
            "messages": [
                {
                    "id": "1",
                    "content": "Hello from Discord!",
                    "author": {"name": "Bob", "id": "U1"},
                    "timestamp": "2024-01-15T12:00:00+00:00",
                }
            ]
        }
        files = [("file", ("discord.json", io.BytesIO(json.dumps(data).encode()), "application/json"))]
        resp = app_client.post("/ingest/discord", headers=auth_headers, files=files)
        assert resp.status_code == 200


class TestTaskIngestion:
    def test_ingest_tasks_json(self, app_client, auth_headers):
        tasks = [
            {
                "id": "T-1",
                "title": "Fix login bug",
                "assignee": "alice",
                "status": "done",
                "description": "Login was broken on mobile",
            }
        ]
        files = [("file", ("tasks.json", io.BytesIO(json.dumps(tasks).encode()), "application/json"))]
        resp = app_client.post("/ingest/tasks", headers=auth_headers, files=files)
        assert resp.status_code == 200


class TestZipPathTraversal:
    def test_zip_traversal_blocked(self, app_client, auth_headers):
        """A zip with '../' entries must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/passwd", "root:x:0:0")
        buf.seek(0)
        files = [("file", ("evil.zip", buf, "application/zip"))]
        resp = app_client.post("/ingest/slack", headers=auth_headers, files=files)
        assert resp.status_code == 400
