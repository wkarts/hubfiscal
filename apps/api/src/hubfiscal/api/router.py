from fastapi import APIRouter, Depends

from ..dependencies import require_resource
from .routes import (
    access_profiles,
    api_clients,
    audit,
    auth,
    certificates,
    company_lookup,
    dashboard,
    documents,
    health,
    integrations,
    jobs,
    legal_entities,
    plugins,
    policies,
    profile,
    tenants,
    users,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(dashboard.router, dependencies=[Depends(require_resource("dashboard"))])
api_router.include_router(tenants.router)
api_router.include_router(company_lookup.router)
api_router.include_router(access_profiles.router)
api_router.include_router(users.router)
api_router.include_router(legal_entities.router)
api_router.include_router(certificates.router)
api_router.include_router(plugins.router, dependencies=[Depends(require_resource("plugins"))])
api_router.include_router(policies.router, dependencies=[Depends(require_resource("policies"))])
# Documentos aplica internamente `documents` ou o recurso fiscal específico (nfe/cte/nfse/etc.).
api_router.include_router(documents.router)
api_router.include_router(jobs.router)
api_router.include_router(api_clients.router, dependencies=[Depends(require_resource("api_clients"))])
# Integrações usam credenciais OAuth/client-credentials e escopos próprios; não herdam o contexto de usuário.
api_router.include_router(integrations.router)
api_router.include_router(webhooks.router, dependencies=[Depends(require_resource("webhooks"))])
api_router.include_router(audit.router, dependencies=[Depends(require_resource("audit"))])
