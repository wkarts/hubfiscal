from hubfiscal.services.company_lookup import format_cnpj, normalize_tax_document, validate_cnpj, validate_tax_document


def test_numeric_cnpj_is_supported() -> None:
    assert validate_cnpj("19.131.243/0001-97")
    assert validate_tax_document("19.131.243/0001-97")
    assert format_cnpj("19131243000197") == "19.131.243/0001-97"


def test_alphanumeric_cnpj_is_supported() -> None:
    document = "12.ABC.345/01DE-35"
    assert normalize_tax_document(document) == "12ABC34501DE35"
    assert validate_cnpj(document)
    assert validate_tax_document(document.lower())
    assert format_cnpj(document) == "12.ABC.345/01DE-35"


def test_cnpj_rejects_invalid_check_digits_and_invalid_shape() -> None:
    assert not validate_cnpj("12.ABC.345/01DE-00")
    assert not validate_cnpj("12.ABC.345/01DE-AA")
    assert not validate_cnpj("00.000.000/0000-00")
