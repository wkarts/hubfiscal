import base64
import gzip
from uuid import uuid4

import pytest

from hubfiscal.models import LegalEntity
from hubfiscal.operational_schemas import PasswordChange, RetrievalBatchCreate
from hubfiscal.plugins.builtin import NFeDistributionPlugin
from hubfiscal.plugins.sdk import PluginRequest, PluginStatus


def test_batch_deduplicates_keys():
    payload = RetrievalBatchCreate(
        access_keys=[" 29260000000000000000000000000000000000000001 ", "29260000000000000000000000000000000000000001", "35260000000000000000000000000000000000000002"],
    )
    assert payload.access_keys == [
        "29260000000000000000000000000000000000000001",
        "35260000000000000000000000000000000000000002",
    ]


def test_password_change_rejects_edge_spaces():
    with pytest.raises(ValueError):
        PasswordChange(current_password="old-password", new_password=" new-password ")


def _entity() -> LegalEntity:
    return LegalEntity(
        id=uuid4(),
        tenant_id=uuid4(),
        document="11222333000181",
        legal_name="Empresa CI Ltda",
        enabled_resources=["query", "nfe", "dfe"],
    )


def test_nfe_distribution_builds_environment_and_operations():
    plugin = NFeDistributionPlugin()
    entity = _entity()
    request = PluginRequest(
        tenant_id=entity.tenant_id,
        legal_entity_id=entity.id,
        document_type="nfe",
        access_key="29260000000000000000000000000000000000000001",
        operation="consChNFe",
        environment="homologation",
    )
    payload = plugin._payload(entity=entity, cuf="29", request=request).decode()
    assert "<tpAmb>2</tpAmb>" in payload
    assert "<cUFAutor>29</cUFAutor>" in payload
    assert "<CNPJ>11222333000181</CNPJ>" in payload
    assert "<consChNFe>" in payload
    assert "29260000000000000000000000000000000000000001" in payload

    request.operation = "distNSU"
    request.access_key = None
    request.parameters = {"ult_nsu": "123"}
    payload = plugin._payload(entity=entity, cuf="29", request=request).decode()
    assert "<distNSU><ultNSU>000000000000123</ultNSU></distNSU>" in payload


def test_nfe_distribution_decodes_doczip_and_cursor():
    plugin = NFeDistributionPlugin()
    access_key = "29260000000000000000000000000000000000000001"
    xml = f"""<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
    <chNFe>{access_key}</chNFe><CNPJ>11222333000181</CNPJ><xNome>Empresa CI</xNome>
    <IE>123</IE><dhEmi>2026-08-07T00:00:00-03:00</dhEmi><tpNF>1</tpNF><vNF>10.00</vNF>
    <digVal>AA==</digVal><dhRecbto>2026-08-07T00:01:00-03:00</dhRecbto><nProt>1</nProt><cSitNFe>1</cSitNFe>
    </resNFe>""".encode()
    encoded = base64.b64encode(gzip.compress(xml)).decode()
    soap = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
      <soap:Body><retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
        <tpAmb>1</tpAmb><verAplic>1</verAplic><cStat>138</cStat><xMotivo>Documento localizado</xMotivo>
        <dhResp>2026-08-07T00:00:00-03:00</dhResp><ultNSU>000000000000123</ultNSU><maxNSU>000000000000456</maxNSU>
        <loteDistDFeInt><docZip NSU="000000000000123" schema="resNFe_v1.01.xsd">{encoded}</docZip></loteDistDFeInt>
      </retDistDFeInt></soap:Body>
    </soap:Envelope>""".encode()
    result = plugin._parse_response(soap, access_key)
    assert result.status == PluginStatus.FOUND
    assert result.metadata["cstat"] == "138"
    assert result.metadata["ult_nsu"] == "000000000000123"
    assert result.metadata["max_nsu"] == "000000000000456"
    assert len(result.documents) == 1
    assert result.documents[0].xml == xml
    assert result.documents[0].nsu == "000000000000123"


def test_nfe_distribution_cstat_656_is_rate_limited():
    plugin = NFeDistributionPlugin()
    soap = b"""<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
      <tpAmb>1</tpAmb><cStat>656</cStat><xMotivo>Consumo indevido</xMotivo>
      <ultNSU>000000000000100</ultNSU><maxNSU>000000000000200</maxNSU>
    </retDistDFeInt>"""
    result = plugin._parse_response(soap, None)
    assert result.status == PluginStatus.RATE_LIMITED
    assert result.retry_after_seconds == 3600
