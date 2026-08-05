from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import RoutingPolicy
from ...schemas import RoutingPolicyCreate, RoutingPolicyOut

router = APIRouter(prefix="/routing-policies", tags=["Políticas de roteamento"])


@router.get("", response_model=list[RoutingPolicyOut])
async def list_policies(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: return []
    return list((await db.scalars(select(RoutingPolicy).where(RoutingPolicy.tenant_id == context.tenant_id).order_by(RoutingPolicy.name))).all())


@router.post("", response_model=RoutingPolicyOut, status_code=201)
async def create_policy(payload: RoutingPolicyCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    item = RoutingPolicy(tenant_id=context.tenant_id, **payload.model_dump())
    db.add(item); await db.commit(); await db.refresh(item)
    return item
