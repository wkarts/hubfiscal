from hubfiscal.services.xml import parse_xml

def test_parse_nfe_proc():
    key = "1" * 44
    xml = f"""<nfeProc><NFe><infNFe Id="NFe{key}"><emit><CNPJ>12345678000190</CNPJ></emit><dest><CNPJ>98765432000100</CNPJ></dest><total><ICMSTot><vNF>10.50</vNF></ICMSTot></total></infNFe><Signature/></NFe><protNFe><infProt><chNFe>{key}</chNFe></infProt></protNFe></nfeProc>""".encode()
    parsed = parse_xml(xml)
    assert parsed.access_key == key
    assert parsed.document_type == "nfe"
    assert parsed.document_level == "complete"
    assert parsed.total_amount is not None
