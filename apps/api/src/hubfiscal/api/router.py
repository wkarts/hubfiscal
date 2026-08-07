from fastapi import APIRouter

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
    tenants,
    users,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(tenants.router)
api_router.include_router(company_lookup.router)
api_router.include_router(access_profiles.router)
api_router.include_router(users.router)
api_router.include_router(legal_entities.router)
api_router.include_router(certificates.router)
api_router.include_router(plugins.router)
api_router.include_router(policies.router)
api_router.include_router(documents.router)
api_router.include_router(jobs.router)
api_router.include_router(api_clients.router)
api_router.include_router(integrations.router)
api_router.include_router(webhooks.router)
api_router.include_router(audit.router)
