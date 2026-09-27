from fastapi import APIRouter, Cookie, Depends, Response

from app.config import get_settings
from app.core.deps import get_current_admin
from app.core.errors import UnauthorizedError
from app.core.security import TokenError, create_access_token, decode_token
from app.modules.admins.repository import AdminRepository
from app.modules.admins.schemas import AdminOut
from app.modules.auth.schemas import AuthResponse, GoogleLoginRequest
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    # Local dev serves frontend/backend on different localhost ports, which
    # browsers treat as same-site, so Lax + non-Secure works over plain HTTP.
    # A cross-domain production deployment needs SameSite=None + Secure.
    is_prod = settings.environment == "production"
    same_site = "none" if is_prod else "lax"

    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=is_prod,
        samesite=same_site,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=is_prod,
        samesite=same_site,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        # Must match access_token's path. The frontend proxies all API calls
        # through a same-origin "/api/..." prefix, so a cookie scoped to
        # "/auth" never path-matches "/api/auth/refresh" and is silently
        # dropped by the browser, breaking refresh entirely in production.
        path="/",
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(payload: GoogleLoginRequest, response: Response) -> AuthResponse:
    admin, access_token, refresh_token = await AuthService().authenticate_with_google(
        payload.id_token
    )
    _set_auth_cookies(response, access_token, refresh_token)
    return AuthResponse(admin=admin)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response, refresh_token: str | None = Cookie(default=None)
) -> AuthResponse:
    if not refresh_token:
        raise UnauthorizedError("Missing refresh token")

    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    admin = await AdminRepository().get_by_id(payload["sub"])
    if admin is None or not admin.is_active:
        raise UnauthorizedError("Admin not found or inactive")

    new_access_token = create_access_token(admin.id, admin.email)
    _set_auth_cookies(response, new_access_token, refresh_token)
    return AuthResponse(admin=admin)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=AdminOut)
async def me(current_admin: AdminOut = Depends(get_current_admin)) -> AdminOut:
    return current_admin
