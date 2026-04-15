import os
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.schemas.requests import (
    MarkdownIngestRequest,
    GitIngestRequest,
    NotionIngestRequest,
    GoogleDocsIngestRequest,
    ConfluenceIngestRequest,
)
from app.schemas.responses import IngestionResponse
from app.models.artifact import ArtifactRecord
from app.models.member import MemberRecord
from app.models.contribution import ContributionRecord
from app.db.database import create_session
from app.dependencies import require_role

router = APIRouter()


def _get_db():
    return create_session()


def _resolve_or_create_member(db: Session, member_info: dict) -> MemberRecord:
    """Find existing member by alias match or create new one."""
    import re
    member_id = member_info.get("id", "").strip()
    if member_id:
        existing = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if existing:
            return existing

    # Check name match using SQL ILIKE (much faster than loading all members)
    name = member_info.get("name", "").strip()
    if name:
        # Try exact name match first (case-insensitive)
        match = (
            db.query(MemberRecord)
            .filter(MemberRecord.name.ilike(name))
            .first()
        )
        if match:
            return match

        # For alias matching, we still need to check JSON arrays.
        # But limit the search to a reasonable set using name-based heuristic.
        # Check if name appears as substring in any member's name
        partial_match = (
            db.query(MemberRecord)
            .filter(MemberRecord.name.ilike(f"%{name}%"))
            .first()
        )
        if partial_match:
            return partial_match

    # Generate a proper slug ID if none provided
    if not member_id:
        if name:
            member_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        else:
            member_id = str(uuid4())[:8]

    # Create new
    member = MemberRecord(
        id=member_id,
        name=name or member_id,
        aliases=member_info.get("aliases", []),
        email=member_info.get("email"),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def _run_ingestion(request: Request, connector, source_input, source_path: str, room_id: str | None = None):
    """Common ingestion pipeline: parse → embed → store → record."""
    db = _get_db()
    try:
        embedder = request.app.state.embedding_service
        vs = request.app.state.vector_store

        # Parse
        chunks = connector.parse(source_input)
        members_info = connector.extract_members(source_input)

        # Resolve members
        member_ids = []
        for mi in members_info:
            member = _resolve_or_create_member(db, mi)
            member_ids.append(member.id)

        # Create artifact record
        artifact_id = str(uuid4())
        artifact = ArtifactRecord(
            id=artifact_id,
            source_type=connector.source_type(),
            source_path=source_path,
            title=source_path.split("/")[-1],
            chunk_count=len(chunks),
            member_ids=member_ids,
            status="completed",
            room_id=room_id,
        )
        db.add(artifact)

        # Embed and store chunks
        if chunks:
            texts = [c.text for c in chunks]
            embeddings = embedder.embed_batch(texts)

            ids = [f"chunk-{uuid4()}" for _ in chunks]
            documents = texts
            metadatas = []
            for c in chunks:
                meta = {
                    "source_type": c.source_type,
                    "source_ref": c.source_ref,
                    "artifact_id": artifact_id,
                    "author": c.author or "unknown",
                    "timestamp": c.timestamp.isoformat() if c.timestamp else "",
                    "topics": ",".join(c.topics),
                    "room_id": room_id or "",
                }
                metadatas.append(meta)

            vs.add_documents(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

            # Create contribution records for chunks with authors
            for c in chunks:
                if c.author:
                    author_id = c.author.lower().replace(" ", "-")
                    member = db.query(MemberRecord).filter(MemberRecord.id == author_id).first()
                    if member:
                        contrib = ContributionRecord(
                            id=str(uuid4()),
                            member_id=member.id,
                            artifact_id=artifact_id,
                            contribution_type=f"{c.source_type}_content",
                            timestamp=c.timestamp,
                            description=c.text[:200],
                            topics=c.topics,
                            room_id=room_id,
                        )
                        db.add(contrib)
                        member.total_contributions = (member.total_contributions or 0) + 1
                        if c.timestamp and (not member.last_active or c.timestamp > member.last_active):
                            member.last_active = c.timestamp
                        # Update expertise tags
                        existing_tags = set(member.expertise_tags or [])
                        existing_tags.update(c.topics)
                        member.expertise_tags = list(existing_tags)

        db.commit()

        # Invalidate cached graph so new data is reflected
        from app.services.memory_graph import invalidate_graph_cache
        invalidate_graph_cache(room_id=room_id)

        return IngestionResponse(
            artifact_id=artifact_id,
            source_type=connector.source_type(),
            status="completed",
            chunk_count=len(chunks),
            member_count=len(member_ids),
        )
    finally:
        db.close()


_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB per file


async def _read_upload(uploaded: UploadFile, max_bytes: int = _MAX_UPLOAD_BYTES) -> bytes:
    """Read an uploaded file with size enforcement."""
    content = await uploaded.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File '{uploaded.filename}' exceeds {max_bytes // (1024*1024)}MB limit.",
        )
    return content


_MAX_ZIP_DECOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB max decompressed size


def _safe_extract_zip(zf, target_dir: str, allowed_extensions: tuple | None = None):
    """Extract ZIP members safely, rejecting any that escape target_dir (ZipSlip)."""
    target = os.path.realpath(target_dir)

    # Check total decompressed size to prevent ZIP bombs
    total_size = sum(info.file_size for info in zf.infolist() if not info.is_dir())
    if total_size > _MAX_ZIP_DECOMPRESSED_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"ZIP decompressed size ({total_size // (1024*1024)}MB) exceeds limit ({_MAX_ZIP_DECOMPRESSED_BYTES // (1024*1024)}MB).",
        )

    for member in zf.namelist():
        # Skip directories
        if member.endswith("/"):
            continue
        # Reject hidden files and system files
        basename = os.path.basename(member)
        if basename.startswith(".") or basename.startswith("__"):
            continue
        # Filter by extension if specified
        if allowed_extensions and not member.lower().endswith(allowed_extensions):
            continue
        # Resolve the final destination and ensure it stays within target_dir
        dest = os.path.realpath(os.path.join(target, member))
        if not dest.startswith(target + os.sep) and dest != target:
            raise HTTPException(
                status_code=400,
                detail=f"Zip entry attempts path traversal: {member}",
            )
        # Create parent directories safely
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # Extract individual member
        with zf.open(member) as src, open(dest, "wb") as dst:
            dst.write(src.read())


import re as _re

_SAFE_FILENAME_RE = _re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\- ]{0,254}$")


def _sanitize_filename(name: str) -> str:
    """Strip directory components and validate filename safety."""
    # Handle both Unix and Windows path separators
    basename = os.path.basename(name.replace("\\", "/"))
    # Reject hidden files, empty names, and dangerous characters
    if not basename or basename.startswith("."):
        basename = "upload_" + basename.lstrip(".")
    # Replace control characters and problematic chars
    basename = _re.sub(r"[^\w.\- ]", "_", basename)
    # Truncate to 255 chars
    return basename[:255]


def _get_allowed_base_dirs() -> list[str]:
    """Return the list of directories that local path ingestion is restricted to."""
    # Allow the working directory and /data (HF Spaces persistent volume)
    base_dirs = [os.path.realpath(os.getcwd())]
    if os.path.isdir("/data"):
        base_dirs.append(os.path.realpath("/data"))
    # Allow additional dirs via CB_ALLOWED_INGEST_DIRS (comma-separated)
    extra = os.environ.get("CB_ALLOWED_INGEST_DIRS", "")
    for d in extra.split(","):
        d = d.strip()
        if d and os.path.isdir(d):
            base_dirs.append(os.path.realpath(d))
    return base_dirs


def _validate_local_path(path: str) -> str:
    """Resolve and validate a local filesystem path.

    Prevents path traversal AND restricts to an allow-listed set of base
    directories (working dir, /data, or CB_ALLOWED_INGEST_DIRS).
    """
    resolved = os.path.realpath(path)
    if ".." in os.path.normpath(path).split(os.sep):
        raise HTTPException(status_code=400, detail="Path traversal is not allowed")
    if not os.path.exists(resolved):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")
    # Ensure the resolved path is within an allowed base directory
    allowed = _get_allowed_base_dirs()
    if not any(resolved == base or resolved.startswith(base + os.sep) for base in allowed):
        raise HTTPException(
            status_code=403,
            detail="Access denied: path is outside allowed directories",
        )
    return resolved


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """Check the status of an async ingestion task."""
    from app.dependencies import get_current_user
    get_current_user(request)

    task_queue = request.app.state.task_queue
    task_result = task_queue.get_result(task_id)
    if task_result is None:
        raise HTTPException(status_code=404, detail="Task not found")

    response = {
        "task_id": task_result.task_id,
        "status": task_result.status.value,
    }
    if task_result.result is not None:
        response["result"] = task_result.result
    if task_result.error is not None:
        response["error"] = task_result.error
    return response


@router.post("/markdown", response_model=IngestionResponse)
async def ingest_markdown(body: MarkdownIngestRequest, request: Request, user=Depends(require_role("admin", "member"))):

    resolved_path = _validate_local_path(body.directory_path)
    if not os.path.isdir(resolved_path):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    from app.ingestion.markdown_connector import MarkdownConnector
    settings = request.app.state.settings
    connector = MarkdownConnector(settings.chunk_size, settings.chunk_overlap)
    return _run_ingestion(request, connector, resolved_path, body.directory_path, room_id=body.room_id)


@router.post("/git", response_model=IngestionResponse)
async def ingest_git(body: GitIngestRequest, request: Request, user=Depends(require_role("admin", "member"))):

    import tempfile
    from git import Repo as GitRepo

    repo_path = body.repo_path.strip()
    clone_dir = None
    branch = body.branch

    # Auto-clone if it looks like a URL
    if repo_path.startswith("http://") or repo_path.startswith("https://") or repo_path.startswith("git@"):
        # Validate it looks like a repo URL (must have at least user/repo)
        if repo_path.startswith("http"):
            parts = repo_path.rstrip("/").split("/")
            if len(parts) < 5:  # https://github.com/user/repo = 5 parts minimum
                raise HTTPException(
                    status_code=400,
                    detail="Please enter a full repository URL (e.g. https://github.com/user/repo), not just a profile URL.",
                )
        try:
            clone_dir = tempfile.mkdtemp(prefix="cb_git_")
            # GIT_TERMINAL_PROMPT=0 prevents hanging on auth prompt for private repos
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            cloned = GitRepo.clone_from(repo_path, clone_dir, env=env)
            resolved_path = clone_dir
            # Auto-detect the default branch from the cloned repo
            branch = cloned.active_branch.name
        except Exception as e:
            if clone_dir and os.path.exists(clone_dir):
                import shutil
                shutil.rmtree(clone_dir, ignore_errors=True)
            err_msg = str(e)
            if "could not read Username" in err_msg or "Authentication failed" in err_msg:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot clone this repository. Only public repositories are supported. Make sure the URL is correct and the repo is public.",
                )
            raise HTTPException(status_code=400, detail=f"Failed to clone repository: {e}")
    else:
        resolved_path = _validate_local_path(repo_path)
        if not os.path.isdir(resolved_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

    try:
        from app.ingestion.git_connector import GitConnector
        settings = request.app.state.settings
        connector = GitConnector(
            branch=branch,
            since_days=body.since_days,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        return _run_ingestion(request, connector, resolved_path, repo_path, room_id=body.room_id)
    finally:
        if clone_dir and os.path.exists(clone_dir):
            import shutil
            shutil.rmtree(clone_dir, ignore_errors=True)


@router.post("/markdown-upload", response_model=IngestionResponse)
async def ingest_markdown_upload(request: Request, files: list[UploadFile] = File(...), room_id: str | None = None, user=Depends(require_role("admin", "member"))):
    """Upload .md, .txt, or .zip files to ingest as markdown docs."""

    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory(prefix="cb_md_") as tmpdir:
        doc_dir = os.path.join(tmpdir, "docs")
        os.makedirs(doc_dir)

        for uploaded in files:
            filename = _sanitize_filename(uploaded.filename or "document.md")
            content = await _read_upload(uploaded)
            file_path = os.path.join(tmpdir, filename)
            with open(file_path, "wb") as f:
                f.write(content)

            # If ZIP, extract markdown files from it (safe extraction)
            if filename.lower().endswith(".zip") and zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, "r") as zf:
                    _safe_extract_zip(zf, doc_dir, allowed_extensions=(".md", ".txt", ".markdown"))
            elif filename.lower().endswith((".md", ".txt", ".markdown")):
                dest = os.path.join(doc_dir, filename)
                with open(dest, "wb") as f:
                    f.write(content)

        # Check we have something to ingest
        md_files = []
        for root, _, fnames in os.walk(doc_dir):
            for fname in fnames:
                if fname.lower().endswith((".md", ".txt", ".markdown")):
                    md_files.append(fname)

        if not md_files:
            raise HTTPException(
                status_code=400,
                detail="No markdown files found. Upload .md, .txt, or a .zip containing them.",
            )

        from app.ingestion.markdown_connector import MarkdownConnector
        settings = request.app.state.settings
        connector = MarkdownConnector(settings.chunk_size, settings.chunk_overlap)

        upload_names = ", ".join(f.filename or "file" for f in files)
        return _run_ingestion(request, connector, doc_dir, f"upload: {upload_names}", room_id=room_id)


@router.post("/slack", response_model=IngestionResponse)
async def ingest_slack(request: Request, file: UploadFile = File(...), room_id: str | None = None, user=Depends(require_role("admin", "member"))):

    import tempfile, zipfile, os
    from app.ingestion.slack_connector import SlackConnector
    settings = request.app.state.settings

    # Save uploaded ZIP to temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, _sanitize_filename(file.filename or "slack_export.zip"))
        content = await _read_upload(file)
        with open(zip_path, "wb") as f:
            f.write(content)

        # Extract if ZIP (safe extraction — prevents path traversal)
        extract_dir = os.path.join(tmpdir, "extracted")
        if zipfile.is_zipfile(zip_path):
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                _safe_extract_zip(zf, extract_dir)
        else:
            extract_dir = zip_path

        connector = SlackConnector(settings.chunk_size, settings.chunk_overlap)
        return _run_ingestion(request, connector, extract_dir, file.filename or "slack_export", room_id=room_id)


@router.post("/discord", response_model=IngestionResponse)
async def ingest_discord(request: Request, file: UploadFile = File(...), room_id: str | None = None, user=Depends(require_role("admin", "member"))):

    import tempfile, os
    from app.ingestion.discord_connector import DiscordConnector
    settings = request.app.state.settings

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, _sanitize_filename(file.filename or "discord_export.json"))
        content = await _read_upload(file)
        with open(file_path, "wb") as f:
            f.write(content)

        connector = DiscordConnector(settings.chunk_size, settings.chunk_overlap)
        return _run_ingestion(request, connector, file_path, file.filename or "discord_export", room_id=room_id)


@router.post("/tasks", response_model=IngestionResponse)
async def ingest_tasks(request: Request, file: UploadFile = File(...), room_id: str | None = None, user=Depends(require_role("admin", "member"))):

    import tempfile, os
    from app.ingestion.task_connector import TaskConnector
    settings = request.app.state.settings

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, _sanitize_filename(file.filename or "tasks.json"))
        content = await _read_upload(file)
        with open(file_path, "wb") as f:
            f.write(content)

        connector = TaskConnector(settings.chunk_size, settings.chunk_overlap)
        return _run_ingestion(request, connector, file_path, file.filename or "tasks", room_id=room_id)


@router.post("/documents", response_model=IngestionResponse)
async def ingest_documents(request: Request, files: list[UploadFile] = File(...), room_id: str | None = None, user=Depends(require_role("admin", "member"))):
    """Upload PDF, DOCX, or TXT files to ingest as documents."""

    import tempfile

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

    with tempfile.TemporaryDirectory(prefix="cb_doc_") as tmpdir:
        saved_paths = []

        for uploaded in files:
            filename = _sanitize_filename(uploaded.filename or "document.txt")
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
                )

            file_path = os.path.join(tmpdir, filename)
            content = await _read_upload(uploaded)
            with open(file_path, "wb") as f:
                f.write(content)
            saved_paths.append(file_path)

        if not saved_paths:
            raise HTTPException(status_code=400, detail="No files uploaded.")

        from app.ingestion.document_connector import DocumentConnector
        settings = request.app.state.settings
        connector = DocumentConnector(settings.chunk_size, settings.chunk_overlap)

        # Parse all files and combine chunks
        all_chunks = []
        for fp in saved_paths:
            all_chunks.extend(connector.parse(fp))

        if not all_chunks:
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the uploaded files. They may be empty or image-only.",
            )

        # Use the common ingestion pipeline for embedding + storage
        # We override _run_ingestion since we already have chunks from multiple files
        db = _get_db()
        try:
            embedder = request.app.state.embedding_service
            vs = request.app.state.vector_store

            from uuid import uuid4
            artifact_id = str(uuid4())
            upload_names = ", ".join(f.filename or "file" for f in files)
            artifact = ArtifactRecord(
                id=artifact_id,
                source_type="document",
                source_path=f"upload: {upload_names}",
                title=upload_names[:100],
                chunk_count=len(all_chunks),
                member_ids=[],
                status="completed",
                room_id=room_id,
            )
            db.add(artifact)

            texts = [c.text for c in all_chunks]
            embeddings = embedder.embed_batch(texts)

            ids = [f"chunk-{uuid4()}" for _ in all_chunks]
            metadatas = []
            for c in all_chunks:
                meta = {
                    "source_type": c.source_type,
                    "source_ref": c.source_ref,
                    "artifact_id": artifact_id,
                    "author": c.author or "unknown",
                    "timestamp": c.timestamp.isoformat() if c.timestamp else "",
                    "topics": ",".join(c.topics),
                }
                if room_id:
                    meta["room_id"] = room_id
                metadatas.append(meta)

            vs.add_documents(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
            db.commit()

            from app.services.memory_graph import invalidate_graph_cache
            invalidate_graph_cache(room_id=room_id)
        finally:
            db.close()

        return IngestionResponse(
            artifact_id=artifact_id,
            source_type="document",
            status="completed",
            chunk_count=len(all_chunks),
            member_count=0,
        )


# ── Phase 5: External integration ingest endpoints ────────────────────────────

@router.post("/notion", response_model=IngestionResponse)
async def ingest_notion(
    body: NotionIngestRequest,
    request: Request,
    user=Depends(require_role("admin", "member")),
):
    """Ingest pages from a Notion database or page tree.

    Requires CB_NOTION_TOKEN in .env.
    Provide either database_id (all pages in a DB) or page_id (single page + children).
    """
    settings = request.app.state.settings
    if not settings.notion_token:
        raise HTTPException(
            status_code=400,
            detail="Notion integration not configured. Set CB_NOTION_TOKEN in .env",
        )
    try:
        source_input = body.to_source_input()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.ingestion.notion_connector import NotionConnector
    connector = NotionConnector(
        token=settings.notion_token,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    source_path = f"notion:{body.database_id or body.page_id}"
    return _run_ingestion(request, connector, source_input, source_path, room_id=body.room_id)


@router.post("/google-docs", response_model=IngestionResponse)
async def ingest_google_docs(
    body: GoogleDocsIngestRequest,
    request: Request,
    user=Depends(require_role("admin", "member")),
):
    """Ingest Google Docs from a list of document IDs or a Drive folder.

    Requires CB_GOOGLE_SERVICE_ACCOUNT_FILE or CB_GOOGLE_ACCESS_TOKEN in .env.
    """
    settings = request.app.state.settings
    if not settings.google_service_account_file and not settings.google_access_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google Docs integration not configured. "
                "Set CB_GOOGLE_SERVICE_ACCOUNT_FILE or CB_GOOGLE_ACCESS_TOKEN in .env"
            ),
        )
    try:
        source_input = body.to_source_input()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.ingestion.google_docs_connector import GoogleDocsConnector
    connector = GoogleDocsConnector(
        service_account_file=settings.google_service_account_file or None,
        access_token=settings.google_access_token or None,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    source_path = f"google_docs:{body.folder_id or ','.join(body.document_ids or [])}"
    return _run_ingestion(request, connector, source_input, source_path, room_id=body.room_id)


@router.post("/confluence", response_model=IngestionResponse)
async def ingest_confluence(
    body: ConfluenceIngestRequest,
    request: Request,
    user=Depends(require_role("admin", "member")),
):
    """Ingest pages from a Confluence space or specific page IDs.

    Requires CB_CONFLUENCE_URL, CB_CONFLUENCE_USER, CB_CONFLUENCE_TOKEN in .env.
    """
    settings = request.app.state.settings
    if not settings.confluence_url or not settings.confluence_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Confluence integration not configured. "
                "Set CB_CONFLUENCE_URL, CB_CONFLUENCE_USER, CB_CONFLUENCE_TOKEN in .env"
            ),
        )
    try:
        source_input = body.to_source_input()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.ingestion.confluence_connector import ConfluenceConnector
    connector = ConfluenceConnector(
        url=settings.confluence_url,
        username=settings.confluence_user,
        token=settings.confluence_token,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        cloud=settings.confluence_cloud,
    )
    source_path = f"confluence:{body.space_key or ','.join(body.page_ids or [])}"
    return _run_ingestion(request, connector, source_input, source_path, room_id=body.room_id)
