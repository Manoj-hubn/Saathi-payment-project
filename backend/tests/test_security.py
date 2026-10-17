from app.security import (
    create_challenge, verify_challenge, make_pin_hash, verify_pin,
    create_access_token, verify_access_token, normalize_digits
)

def test_challenge_single_use():
    challenge = create_challenge(10)
    assert verify_challenge(10, challenge["token"], challenge["phrase"])
    assert not verify_challenge(10, challenge["token"], challenge["phrase"])

def test_wrong_user_cannot_use_challenge():
    challenge = create_challenge(10)
    assert not verify_challenge(11, challenge["token"], challenge["phrase"])

def test_digit_normalization():
    assert normalize_digits("four seven two") == "4 7 2"
    assert normalize_digits("chaar saat do") == "4 7 2"
    assert normalize_digits("4, 7, 2") == "4 7 2"

def test_pin():
    hashed = make_pin_hash("1234", "test-salt")
    assert verify_pin(1, "1234", hashed)[0]
    assert not verify_pin(2, "9999", hashed)[0]

def test_jwt_access_token():
    token = create_access_token(1, "customer1", "customer")
    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["username"] == "customer1"
    assert payload["role"] == "customer"

def test_invalid_jwt_access_token():
    assert verify_access_token("invalid.token.structure") is None
    assert verify_access_token("abc.def.ghi") is None
