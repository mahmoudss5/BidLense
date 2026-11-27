from app.core.security import create_access_token, hash_password, verify_password


def test_password_hash_and_verify():
    password = "StrongPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_is_created():
    token = create_access_token("123")
    assert isinstance(token, str)
    assert len(token) > 20
