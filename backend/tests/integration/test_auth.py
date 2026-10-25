import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_auth_full_lifecycle_and_reuse_detection() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"

        # 1. Register new user
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": password,
                "display_name": "Test User",
            },
        )
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert "access_token" in reg_data
        assert "refresh_token" in reg_data
        assert reg_data["token_type"] == "bearer"

        # 2. Duplicate registration fails with 409
        dup_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": password,
            },
        )
        assert dup_res.status_code == 409
        dup_json = dup_res.json()
        assert "error" in dup_json
        assert dup_json["error"]["code"] == "VALIDATION_FAILED"

        # 3. Login with correct password
        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": password,
            },
        )
        assert login_res.status_code == 200
        tokens = login_res.json()
        access_token_1 = tokens["access_token"]
        refresh_token_1 = tokens["refresh_token"]

        # 4. Login with invalid password fails with 401
        bad_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": "WrongPassword!",
            },
        )
        assert bad_login.status_code == 401
        assert bad_login.json()["error"]["code"] == "AUTH_INVALID"

        # 5. Access /api/v1/auth/me with Bearer token
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token_1}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == test_email
        assert me_data["display_name"] == "Test User"
        assert me_data["llm_enabled"] is True

        # 6. Access /api/v1/auth/me without token fails with 401
        unauth_res = await client.get("/api/v1/auth/me")
        assert unauth_res.status_code == 401

        # 7. Update profile
        patch_res = await client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token_1}"},
            json={"display_name": "Updated Name", "llm_enabled": False},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["display_name"] == "Updated Name"
        assert patch_res.json()["llm_enabled"] is False

        # 8. Rotate refresh token
        rotate_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert rotate_res.status_code == 200
        new_tokens = rotate_res.json()
        access_token_2 = new_tokens["access_token"]
        refresh_token_2 = new_tokens["refresh_token"]
        assert refresh_token_2 != refresh_token_1

        # Verify new access token works
        me_res_2 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token_2}"},
        )
        assert me_res_2.status_code == 200

        # 9. REPLAY ATTACK TEST: Presenting old refresh_token_1 must trigger reuse detection
        replay_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert replay_res.status_code == 401
        assert "reuse detected" in replay_res.json()["error"]["message"].lower()

        # 10. And because reuse was detected, the newest refresh token (refresh_token_2)
        # must also be revoked due to token family revocation!
        revoked_fam_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_2},
        )
        assert revoked_fam_res.status_code == 401

        # 11. Logout test with fresh login
        relogin = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": password},
        )
        assert relogin.status_code == 200
        logout_token = relogin.json()["refresh_token"]

        logout_res = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": logout_token},
        )
        assert logout_res.status_code == 200
        assert logout_res.json() == {"status": "logged_out"}

        # Attempting to refresh with logged-out token fails
        post_logout = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": logout_token},
        )
        assert post_logout.status_code == 401
