import os

import pytest
import requests


BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8080").rstrip("/")

ROLE_USERS = {
    "admin": {
        "email_or_username": os.environ.get("ADMIN_EMAIL", "admin"),
        "password": os.environ.get("ADMIN_PASSWORD", "Admin@2026"),
    },
    "manager": {"email_or_username": "manager", "password": "Manager@2026"},
    "cashier": {"email_or_username": "cashier", "password": "Cashier@2026"},
}


@pytest.fixture(scope="session")
def sessions():
    result = {}
    for expected_role, credentials in ROLE_USERS.items():
        response = requests.post(f"{BASE_URL}/api/auth/login", json=credentials, timeout=20)
        assert response.status_code == 200, f"login failed for {expected_role}: HTTP {response.status_code}"
        payload = response.json()
        assert payload.get("user", {}).get("role") == expected_role
        token = payload.get("access_token")
        assert token
        result[expected_role] = requests.Session()
        result[expected_role].headers.update({"Authorization": f"Bearer {token}"})
    return result


def test_each_role_can_login_and_read_own_identity(sessions):
    for expected_role, session in sessions.items():
        response = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert response.status_code == 200
        assert response.json().get("role") == expected_role


def test_admin_only_endpoint_rejects_manager_and_cashier(sessions):
    for role in ("manager", "cashier"):
        response = sessions[role].get(f"{BASE_URL}/api/admin/system/mode", timeout=15)
        assert response.status_code == 403, f"{role} unexpectedly received HTTP {response.status_code}"


def test_admin_only_endpoint_is_available_to_admin(sessions):
    response = sessions["admin"].get(f"{BASE_URL}/api/admin/system/mode", timeout=15)
    assert response.status_code == 200


def test_logout_invalidates_cookie_path_without_exposing_token(sessions):
    response = sessions["cashier"].post(f"{BASE_URL}/api/auth/logout", timeout=15)
    assert response.status_code == 200
    assert response.json().get("detail") == "Logged out"


def test_supplier_endpoint_role_matrix(sessions):
    cashier_response = sessions["cashier"].get(f"{BASE_URL}/api/suppliers", timeout=15)
    manager_response = sessions["manager"].get(f"{BASE_URL}/api/suppliers", timeout=15)
    admin_response = sessions["admin"].get(f"{BASE_URL}/api/suppliers", timeout=15)

    assert cashier_response.status_code == 403
    assert manager_response.status_code == 200
    assert admin_response.status_code == 200


def test_cookie_session_is_invalidated_after_logout():
    credentials = ROLE_USERS["cashier"]
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/api/auth/login", json=credentials, timeout=20)
    assert login_response.status_code == 200
    assert "access_token" in session.cookies

    me_before = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me_before.status_code == 200
    assert me_before.json().get("role") == "cashier"

    logout_response = session.post(f"{BASE_URL}/api/auth/logout", timeout=15)
    assert logout_response.status_code == 200

    me_after = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me_after.status_code in (401, 403)
