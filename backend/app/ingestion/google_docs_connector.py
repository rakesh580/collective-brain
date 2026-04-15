"""Google Docs connector — ingests documents from Google Drive or a doc list.

Authentication: Service Account JSON key file path (CB_GOOGLE_SERVICE_ACCOUNT_FILE)
                OR OAuth2 access token (CB_GOOGLE_ACCESS_TOKEN) for user-delegated auth.

Source input:  dict with keys:
                 "document_ids"  — list of Google Doc IDs, OR
                 "folder_id"     — ingest all Docs in a Drive folder

Requires:  google-api-python-client, google-auth
"""
import logging
from datetime import datetime

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.chunker import ChunkingStrategy
from app.ingestion.utils import content_hash, extract_topics_from_text

logger = logging.getLogger("collective_brain.ingestion.google_docs")


def _build_services(service_account_file: str | None, access_token: str | None):
    """Return (docs_service, drive_service) using service account or access token."""
    try:
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "google-api-python-client is not installed. "
            "Run: pip install google-api-python-client google-auth"
        )

    scopes = [
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    if service_account_file:
        creds = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=scopes
        )
    elif access_token:
        creds = Credentials(token=access_token)
    else:
        raise ValueError(
            "Provide either CB_GOOGLE_SERVICE_ACCOUNT_FILE or CB_GOOGLE_ACCESS_TOKEN"
        )

    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return docs, drive


class GoogleDocsConnector(BaseConnector):
    def __init__(
        self,
        service_account_file: str | None = None,
        access_token: str | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self._docs_svc, self._drive_svc = _build_services(service_account_file, access_token)
        self._chunker = ChunkingStrategy(chunk_size, chunk_overlap)

    def source_type(self) -> str:
        return "google_docs"

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse(self, source_input: dict) -> list[ParsedChunk]:
        chunks: list[ParsedChunk] = []
        doc_ids = self._collect_doc_ids(source_input)
        for doc_id in doc_ids:
            try:
                chunks.extend(self._parse_doc(doc_id))
            except Exception as exc:
                logger.warning("Failed to parse Google Doc %s: %s", doc_id, exc)
        return chunks

    def extract_members(self, source_input: dict) -> list[dict]:
        members: dict[str, dict] = {}
        doc_ids = self._collect_doc_ids(source_input)
        for doc_id in doc_ids:
            try:
                meta = (
                    self._drive_svc.files()
                    .get(fileId=doc_id, fields="lastModifyingUser,owners")
                    .execute()
                )
                for user in [meta.get("lastModifyingUser", {})] + meta.get("owners", []):
                    email = user.get("emailAddress", "")
                    name = user.get("displayName") or email.split("@")[0]
                    if email and email not in members:
                        members[email] = {
                            "id": f"gdoc-{email.split('@')[0][:20]}",
                            "name": name,
                            "email": email,
                            "aliases": [name.lower(), email],
                        }
            except Exception:
                pass
        return list(members.values())

    # ── Private helpers ────────────────────────────────────────────────────────

    def _collect_doc_ids(self, source_input: dict) -> list[str]:
        if "document_ids" in source_input:
            return source_input["document_ids"]
        if "folder_id" in source_input:
            return self._list_folder_docs(source_input["folder_id"])
        raise ValueError("source_input must have 'document_ids' or 'folder_id'")

    def _list_folder_docs(self, folder_id: str) -> list[str]:
        ids = []
        page_token = None
        query = (
            f"'{folder_id}' in parents and "
            "mimeType='application/vnd.google-apps.document' and "
            "trashed=false"
        )
        while True:
            kwargs = {"q": query, "fields": "nextPageToken,files(id)", "pageSize": 100}
            if page_token:
                kwargs["pageToken"] = page_token
            resp = self._drive_svc.files().list(**kwargs).execute()
            ids.extend(f["id"] for f in resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        logger.info("Google Drive folder %s: found %d docs", folder_id, len(ids))
        return ids

    def _parse_doc(self, doc_id: str) -> list[ParsedChunk]:
        doc = self._docs_svc.documents().get(documentId=doc_id).execute()
        title = doc.get("title", "Untitled")
        source_url = f"https://docs.google.com/document/d/{doc_id}"

        # Get last modifier from Drive metadata
        author = None
        last_modified = None
        try:
            meta = (
                self._drive_svc.files()
                .get(fileId=doc_id, fields="lastModifyingUser,modifiedTime")
                .execute()
            )
            user = meta.get("lastModifyingUser", {})
            author = user.get("displayName") or user.get("emailAddress")
            mod_time = meta.get("modifiedTime")
            if mod_time:
                last_modified = datetime.fromisoformat(mod_time.replace("Z", "+00:00"))
        except Exception:
            pass

        full_text = self._doc_to_text(doc)
        if not full_text.strip():
            return []

        topics = extract_topics_from_text(full_text)
        raw_chunks = self._chunker.split(full_text, metadata={"doc_id": doc_id})

        parsed: list[ParsedChunk] = []
        for rc in raw_chunks:
            chunk_text = rc["text"]
            parsed.append(ParsedChunk(
                text=chunk_text,
                source_type="google_docs",
                source_ref=source_url,
                author=author,
                author_aliases=[author.lower()] if author else [],
                timestamp=last_modified,
                topics=topics,
                chunk_metadata={
                    "doc_id": doc_id,
                    "title": title,
                    "source_url": source_url,
                    "content_hash": content_hash(chunk_text),
                    **rc.get("metadata", {}),
                },
            ))
        return parsed

    @staticmethod
    def _doc_to_text(doc: dict) -> str:
        """Extract plain text from a Google Docs API document object."""
        lines: list[str] = []
        for elem in doc.get("body", {}).get("content", []):
            para = elem.get("paragraph")
            if not para:
                continue
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            texts = []
            for pe in para.get("elements", []):
                run = pe.get("textRun")
                if run:
                    texts.append(run.get("content", ""))
            line = "".join(texts).rstrip("\n")
            if not line.strip():
                continue
            if "HEADING" in style:
                level = style.split("_")[-1]
                prefix = "#" * int(level) if level.isdigit() else "#"
                lines.append(f"{prefix} {line}")
            else:
                lines.append(line)
        return "\n".join(lines)
