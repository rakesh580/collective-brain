import re
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.db.database import create_session
from app.dependencies import require_role
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.schemas.requests import MemberAliasUpdate, MemberCreateRequest, MemberUpdateRequest
from app.schemas.responses import ContributionResponse, MemberDetailResponse, MemberResponse

router = APIRouter()


def _get_db():
    return create_session()


@router.get("")
async def list_members(request: Request, room_id: str | None = None, limit: int = 50, offset: int = 0):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        if room_id:
            # Only members with contributions in this room
            member_ids = [
                mid for (mid,) in
                db.query(ContributionRecord.member_id)
                .filter(ContributionRecord.room_id == room_id)
                .distinct()
                .all()
            ]
            if member_ids:
                base_query = (
                    db.query(MemberRecord)
                    .filter(MemberRecord.id.in_(member_ids))
                    .order_by(MemberRecord.name)
                )
                total = base_query.count()
                members = base_query.offset(offset).limit(limit).all()
            else:
                total = 0
                members = []
        else:
            base_query = db.query(MemberRecord).order_by(MemberRecord.name)
            total = base_query.count()
            members = base_query.offset(offset).limit(limit).all()
        return {
            "members": [_to_response(m) for m in members],
            "total": total,
        }
    finally:
        db.close()


@router.get("/{member_id}", response_model=MemberDetailResponse)
async def get_member(member_id: str, request: Request, room_id: str | None = None):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        contrib_query = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.member_id == member_id)
        )
        if room_id:
            contrib_query = contrib_query.filter(ContributionRecord.room_id == room_id)
        contribs = (
            contrib_query
            .order_by(ContributionRecord.timestamp.desc())
            .limit(50)
            .all()
        )

        resp = _to_response(member)
        return MemberDetailResponse(
            **resp.model_dump(),
            contributions=[
                ContributionResponse(
                    id=c.id,
                    contribution_type=c.contribution_type or "",
                    timestamp=c.timestamp,
                    description=c.description or "",
                    topics=c.topics or [],
                )
                for c in contribs
            ],
        )
    finally:
        db.close()


@router.put("/{member_id}/aliases", response_model=MemberResponse)
async def update_aliases(member_id: str, body: MemberAliasUpdate, request: Request, user=Depends(require_role("admin", "member"))):

    db = _get_db()
    try:
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        member.aliases = body.aliases
        db.commit()
        db.refresh(member)
        return _to_response(member)
    finally:
        db.close()


@router.get("/{member_id}/contributions", response_model=list[ContributionResponse])
async def get_contributions(member_id: str, request: Request, room_id: str | None = None, limit: int = 50):
    from app.dependencies import get_current_user
    get_current_user(request)

    db = _get_db()
    try:
        contrib_query = (
            db.query(ContributionRecord)
            .filter(ContributionRecord.member_id == member_id)
        )
        if room_id:
            contrib_query = contrib_query.filter(ContributionRecord.room_id == room_id)
        contribs = (
            contrib_query
            .order_by(ContributionRecord.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            ContributionResponse(
                id=c.id,
                contribution_type=c.contribution_type or "",
                timestamp=c.timestamp,
                description=c.description or "",
                topics=c.topics or [],
            )
            for c in contribs
        ]
    finally:
        db.close()


@router.post("", response_model=MemberResponse, status_code=201)
async def create_member(body: MemberCreateRequest, request: Request, user=Depends(require_role("admin", "member"))):

    db = _get_db()
    try:
        slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
        member_id = slug or str(uuid4())[:8]
        # Ensure unique ID
        if db.query(MemberRecord).filter(MemberRecord.id == member_id).first():
            member_id = f"{slug}-{uuid4().hex[:6]}"
        now = datetime.now(UTC)
        member = MemberRecord(
            id=member_id,
            name=body.name,
            aliases=[body.name.lower(), slug],
            email=body.email,
            expertise_tags=body.expertise_tags,
            expertise_scores={},
            strengths=body.strengths,
            weaknesses=body.weaknesses,
            first_seen=now,
            last_active=now,
            total_contributions=0,
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        return _to_response(member)
    finally:
        db.close()


@router.put("/{member_id}", response_model=MemberResponse)
async def update_member(member_id: str, body: MemberUpdateRequest, request: Request, user=Depends(require_role("admin", "member"))):

    db = _get_db()
    try:
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if body.name is not None:
            member.name = body.name
        if body.email is not None:
            member.email = body.email
        if body.expertise_tags is not None:
            member.expertise_tags = body.expertise_tags
        if body.strengths is not None:
            member.strengths = body.strengths
        if body.weaknesses is not None:
            member.weaknesses = body.weaknesses
        db.commit()
        db.refresh(member)
        return _to_response(member)
    finally:
        db.close()


@router.delete("/{member_id}")
async def delete_member(member_id: str, request: Request, user=Depends(require_role("admin"))):

    db = _get_db()
    try:
        member = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        db.query(ContributionRecord).filter(
            ContributionRecord.member_id == member_id
        ).delete()
        # Only load artifacts that reference this member (not ALL artifacts)
        artifacts = (
            db.query(ArtifactRecord)
            .filter(ArtifactRecord.member_ids.isnot(None))
            .all()
        )
        for a in artifacts:
            if member_id in (a.member_ids or []):
                a.member_ids = [mid for mid in a.member_ids if mid != member_id]
        db.delete(member)
        db.commit()
        return {"status": "deleted", "member_id": member_id}
    finally:
        db.close()


def _to_response(m: MemberRecord) -> MemberResponse:
    return MemberResponse(
        id=m.id,
        name=m.name,
        aliases=m.aliases or [],
        email=m.email,
        expertise_tags=m.expertise_tags or [],
        expertise_scores=m.expertise_scores or {},
        strengths=m.strengths or [],
        weaknesses=m.weaknesses or [],
        last_active=m.last_active,
        total_contributions=m.total_contributions or 0,
    )
