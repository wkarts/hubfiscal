from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from ...dependencies import current_user
from ...models import User
from ...operational_schemas import PasswordChange, ProfileUpdate
from ...services.audit import audit
from ...services.storage import ObjectStorageError, storage

router = APIRouter(prefix="/profile", tags=["Minha conta"])
logger = structlog.get_logger(__name__)
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def serialize(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "status": user.status,
        "is_platform_admin": user.is_platform_admin,
        "has_avatar": user.has_avatar,
        "password_changed_at": user.password_changed_at,
    }


@router.get("")
async def get_profile(user: User = Depends(current_user)):
    return serialize(user)


@router.patch("")
async def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.lower()
    conflict = await db.scalar(select(User).where(User.email == email, User.id != user.id))
    if conflict:
        raise HTTPException(status_code=409, detail="E-mail já utilizado por outro usuário")
    before = {"name": user.name, "email": user.email}
    user.name = payload.name.strip()
    user.email = email
    await audit(
        db,
        action="profile.update",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        details={"before": before, "after": {"name": user.name, "email": user.email}},
    )
    await db.commit()
    await db.refresh(user)
    return serialize(user)


@router.post("/password", status_code=204)
async def change_password(
    payload: PasswordChange,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=422, detail="Senha atual incorreta")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="A nova senha deve ser diferente da senha atual")
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(UTC)
    await audit(
        db,
        action="profile.password.change",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
    )
    await db.commit()


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=422, detail="Use uma imagem JPEG, PNG ou WebP")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Imagem vazia")
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="A foto deve possuir no máximo 2 MB")
    storage_key = f"users/{user.id}/avatar.enc"
    try:
        await storage.put(storage_key, encrypt_secret(data), "application/octet-stream")
    except ObjectStorageError as exc:
        logger.warning("profile.avatar.storage_failed", user_id=str(user.id), error=str(exc))
        raise HTTPException(status_code=503, detail="Não foi possível gravar a foto no armazenamento") from exc
    user.avatar_storage_key = storage_key
    user.avatar_content_type = content_type
    await audit(
        db,
        action="profile.avatar.update",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        details={"content_type": content_type, "size": len(data)},
    )
    await db.commit()
    return {"has_avatar": True}


@router.get("/avatar")
async def get_avatar(user: User = Depends(current_user)):
    if not user.avatar_storage_key:
        raise HTTPException(status_code=404, detail="Usuário sem foto")
    try:
        encrypted = await storage.get(user.avatar_storage_key)
        data = decrypt_secret(encrypted)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=503, detail="Foto temporariamente indisponível") from exc
    return StreamingResponse(
        BytesIO(data),
        media_type=user.avatar_content_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.delete("/avatar", status_code=204)
async def delete_avatar(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    key = user.avatar_storage_key
    if key:
        try:
            await storage.delete(key)
        except ObjectStorageError:
            logger.warning("profile.avatar.delete_failed", user_id=str(user.id))
    user.avatar_storage_key = None
    user.avatar_content_type = None
    await audit(
        db,
        action="profile.avatar.delete",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
    )
    await db.commit()
