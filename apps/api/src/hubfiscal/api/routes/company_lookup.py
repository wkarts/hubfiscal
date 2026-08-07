from fastapi import APIRouter, Depends, HTTPException, Query

from ...dependencies import AuthContext, current_context
from ...schemas import CompanyLookupOut
from ...services.company_lookup import CompanyLookupError, lookup_company, normalize_tax_document, validate_cnpj

router = APIRouter(prefix="/company-lookup", tags=["Consulta CNPJ"])


@router.get("/{document}", response_model=CompanyLookupOut)
async def company_lookup(
    document: str,
    providers: str | None = Query(default=None, description="Ordem opcional: brasilapi,receitaws"),
    _: AuthContext = Depends(current_context),
):
    normalized = normalize_tax_document(document)
    if not validate_cnpj(normalized):
        raise HTTPException(status_code=422, detail="CNPJ inválido")
    selected = [item.strip().lower() for item in providers.split(",") if item.strip()] if providers else None
    try:
        result = await lookup_company(normalized, selected)
    except CompanyLookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CompanyLookupOut(**result.as_dict())
