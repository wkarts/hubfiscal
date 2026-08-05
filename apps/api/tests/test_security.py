from hubfiscal.core.security import hash_password, verify_password, create_access_token, decode_token

def test_password_hash():
    hashed = hash_password("a-very-safe-password")
    assert verify_password("a-very-safe-password", hashed)
    assert not verify_password("wrong", hashed)

def test_jwt():
    token = create_access_token("abc")
    assert decode_token(token)["sub"] == "abc"
