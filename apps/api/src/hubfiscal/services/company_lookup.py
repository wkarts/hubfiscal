from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

CNPJ_PATTERN = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
CPF_PATTERN = re.compile(r"^[0-9]{11}$")


class CompanyLookupError(RuntimeError):
    pass


def normalize_tax_document(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def format_cnpj(value: str) -> str:
    document = normalize_tax_document(value)
    if len(document) != 14:
        return document
    return f"{document[:2]}.{document[2:5]}.{document[5:8]}/{document[8:12]}-{document[12:]}"


def _cnpj_char_value(char: str) -> int:
    return ord(char) - 48


def _cnpj_digit(base: str, weights: list[int]) -> str:
    total = sum(_cnpj_char_value(char) * weight for char, weight in zip(base, weights, strict=True))
    remainder = total % 11
    digit = 0 if remainder < 2 else 11 - remainder
    return str(digit)


def validate_cnpj(value: str) -> bool:
    document = normalize_tax_document(value)
    if not CNPJ_PATTERN.fullmatch(document):
        return False
    if len(set(document)) == 1:
        return False
    first = _cnpj_digit(document[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _cnpj_digit(document[:12] + first, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return document[-2:] == first + second


def validate_cpf(value: str) -> bool:
    document = normalize_tax_document(value)
    if not CPF_PATTERN.fullmatch(document) or len(set(document)) == 1:
        return False
    numbers = [int(char) for char in document]
    first_sum = sum(numbers[index] * (10 - index) for index in range(9))
    first = (first_sum * 10 % 11) % 10
    second_sum = sum(numbers[index] * (11 - index) for index in range(10))
    second = (second_sum * 10 % 11) % 10
    return numbers[9] == first and numbers[10] == second


def validate_tax_document(value: str) -> bool:
    document = normalize_tax_document(value)
    if len(document) == 14:
        return validate_cnpj(document)
    if len(document) == 11 and document.isdigit():
        return validate_cpf(document)
    return False


@dataclass(slots=True)
class CompanyLookupResult:
    document: str
    formatted_document: str
    legal_name: str = ""
    trade_name: str | None = None
    status: str | None = None
    opening_date: str | None = None
    state_registration: str | None = None
    city_ibge_code: str | None = None
    email: str | None = None
    phone: str | None = None
    address: dict[str, Any] = field(default_factory=dict)
    activities: list[dict[str, Any]] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    raw_by_provider: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: "CompanyLookupResult") -> None:
        for attribute in (
            "legal_name",
            "trade_name",
            "status",
            "opening_date",
            "state_registration",
            "city_ibge_code",
            "email",
            "phone",
        ):
            if not getattr(self, attribute) and getattr(other, attribute):
                setattr(self, attribute, getattr(other, attribute))
        if not self.address and other.address:
            self.address = other.address
        if not self.activities and other.activities:
            self.activities = other.activities
        self.providers.extend(provider for provider in other.providers if provider not in self.providers)
        self.raw_by_provider.update(other.raw_by_provider)
        self.warnings.extend(other.warnings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "formatted_document": self.formatted_document,
            "legal_name": self.legal_name,
            "trade_name": self.trade_name,
            "status": self.status,
            "opening_date": self.opening_date,
            "state_registration": self.state_registration,
            "city_ibge_code": self.city_ibge_code,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "activities": self.activities,
            "providers": self.providers,
            "warnings": self.warnings,
            "raw_by_provider": self.raw_by_provider,
        }


async def _lookup_brasilapi(client: httpx.AsyncClient, document: str) -> CompanyLookupResult:
    response = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{document}")
    if response.status_code == 404:
        raise CompanyLookupError("CNPJ não encontrado na BrasilAPI")
    response.raise_for_status()
    data = response.json()
    activities: list[dict[str, Any]] = []
    if data.get("cnae_fiscal"):
        activities.append({"code": str(data.get("cnae_fiscal")), "text": data.get("cnae_fiscal_descricao")})
    activities.extend(
        {"code": str(item.get("codigo", "")), "text": item.get("descricao")}
        for item in data.get("cnaes_secundarios", [])
    )
    return CompanyLookupResult(
        document=document,
        formatted_document=format_cnpj(document),
        legal_name=data.get("razao_social") or "",
        trade_name=data.get("nome_fantasia") or None,
        status=data.get("descricao_situacao_cadastral") or None,
        opening_date=data.get("data_inicio_atividade") or None,
        city_ibge_code=str(data.get("codigo_municipio_ibge") or "") or None,
        email=data.get("email") or None,
        phone=data.get("ddd_telefone_1") or data.get("ddd_telefone_2") or None,
        address={
            "street": data.get("logradouro"),
            "number": data.get("numero"),
            "complement": data.get("complemento"),
            "district": data.get("bairro"),
            "city": data.get("municipio"),
            "state": data.get("uf"),
            "zip_code": data.get("cep"),
        },
        activities=activities,
        providers=["brasilapi"],
        raw_by_provider={"brasilapi": data},
    )


async def _lookup_receitaws(client: httpx.AsyncClient, document: str) -> CompanyLookupResult:
    response = await client.get(f"https://receitaws.com.br/v1/cnpj/{document}")
    response.raise_for_status()
    data = response.json()
    if data.get("status") == "ERROR":
        raise CompanyLookupError(data.get("message") or "CNPJ indisponível na ReceitaWS")
    activities = [
        {"code": item.get("code"), "text": item.get("text")}
        for item in [*(data.get("atividade_principal") or []), *(data.get("atividades_secundarias") or [])]
    ]
    return CompanyLookupResult(
        document=document,
        formatted_document=format_cnpj(document),
        legal_name=data.get("nome") or "",
        trade_name=data.get("fantasia") or None,
        status=data.get("situacao") or None,
        opening_date=data.get("abertura") or None,
        email=data.get("email") or None,
        phone=data.get("telefone") or None,
        address={
            "street": data.get("logradouro"),
            "number": data.get("numero"),
            "complement": data.get("complemento"),
            "district": data.get("bairro"),
            "city": data.get("municipio"),
            "state": data.get("uf"),
            "zip_code": data.get("cep"),
        },
        activities=activities,
        providers=["receitaws"],
        raw_by_provider={"receitaws": data},
    )


async def lookup_company(document: str, providers: list[str] | None = None) -> CompanyLookupResult:
    normalized = normalize_tax_document(document)
    if len(normalized) != 14 or not validate_cnpj(normalized):
        raise CompanyLookupError("CNPJ inválido, inclusive pelas regras do CNPJ alfanumérico")

    result = CompanyLookupResult(document=normalized, formatted_document=format_cnpj(normalized))
    errors: list[str] = []
    provider_order = providers or ["brasilapi", "receitaws"]
    lookup_map = {"brasilapi": _lookup_brasilapi, "receitaws": _lookup_receitaws}

    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=True) as client:
        for provider in provider_order:
            lookup = lookup_map.get(provider)
            if lookup is None:
                continue
            try:
                provider_result = await lookup(client, normalized)
                result.merge(provider_result)
                if result.legal_name:
                    break
            except (httpx.HTTPError, CompanyLookupError, ValueError) as exc:
                errors.append(f"{provider}: {exc}")

    if not result.legal_name:
        result.warnings.extend(errors)
        raise CompanyLookupError("Nenhum provedor retornou dados para o CNPJ informado: " + "; ".join(errors))
    result.warnings.extend(errors)
    return result
