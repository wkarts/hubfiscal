from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import hash_password
from ...dependencies import AuthContext, current_context
from ...models import Membership, User
from ...schemas import UserCreate, UserOut
from ...services.audit import audit

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("", response_model=list[UserOut])
async def list_users(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        return list((await db.scalars(select(User).order_by(User.name))).all())
    stmt = select(User).join(Membership).where(Membership.tenant_id == context.tenant_id).order_by(User.name)
    return list((await db.scalars(stmt)).unique().all())


@router.post("", response_model=UserOut, status_code=201)
async def create_user(payload: UserCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password))
        db.add(user)
        await db.flush()
    if await db.scalar(select(Membership).where(Membership.tenant_id == context.tenant_id, Membership.user_id == user.id)):
        raise HTTPException(status_code=409, detail="Usuário já pertence ao cliente")
    db.add(Membership(tenant_id=context.tenant_id, user_id=user.id, role=payload.role, permissions=[]))
    await audit(db, action="user.create", resource_type="user", resource_id=str(user.id), tenant_id=context.tenant_id, user_id=context.user.id)
    await db.commit()
    await db.refresh(user)
    return user
