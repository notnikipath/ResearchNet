from shared.researchnet_common import decrypt_text, encrypt_text, has_permission, sign_token, verify_token


def test_encrypt_roundtrip() -> None:
    secret = "demo-key"
    value = "sensitive abstract"
    encrypted = encrypt_text(value, secret)
    assert encrypted != value
    assert decrypt_text(encrypted, secret) == value



def test_token_roundtrip() -> None:
    token = sign_token({"sub": "USR-001", "role": "researcher"}, "jwt-secret", exp_minutes=5)
    payload = verify_token(token, "jwt-secret")
    assert payload is not None
    assert payload["sub"] == "USR-001"



def test_permissions() -> None:
    assert has_permission("reader", "search:query")
    assert has_permission("researcher", "paper:ingest")
    assert has_permission("admin", "audit:read")
