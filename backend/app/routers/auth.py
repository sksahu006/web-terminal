"""
Authentication router handling email/password auth, JWT refresh, and optional GitHub OAuth.
"""

from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import get_settings
from ..core.database import get_db
from ..core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..models.user import User
from ..models.user_limits import UserLimits
from ..schemas.user import (
    AuthTokenResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_tokens(user: User) -> tuple[str, str]:
    payload = {"sub": user.id}
    return create_access_token(payload), create_refresh_token(payload)


async def _create_default_limits(db: AsyncSession, user_id: str) -> None:
    result = await db.execute(select(UserLimits).where(UserLimits.user_id == user_id))
    if result.scalar_one_or_none() is None:
        db.add(UserLimits(user_id=user_id))


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a local email/password user and return JWT tokens."""
    email = _normalize_email(str(payload.email))
    username = payload.username.strip()

    existing_result = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already registered",
        )

    is_admin = username in settings.admin_usernames_list
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        github_id=f"local:{email}",
        github_username=username,
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    await _create_default_limits(db, user.id)
    await db.commit()
    await db.refresh(user)

    access_token, refresh_token = _issue_tokens(user)
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login_user(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login a local email/password user and return JWT tokens."""
    email = _normalize_email(str(payload.email))
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token, refresh_token = _issue_tokens(user)
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    token_payload = decode_access_token(payload.refresh_token)
    if not token_payload or token_payload.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = token_payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    return TokenRefreshResponse(
        access_token=create_access_token({"sub": user.id}),
        refresh_token=payload.refresh_token,
    )


@router.get("/github")
async def github_login():
    """Redirect user to GitHub OAuth authorization page."""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "read:user user:email repo",
        "state": "random_state_string",
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GITHUB_AUTHORIZE_URL}?{query_string}")


@router.get("/github/callback")
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Handle GitHub OAuth callback for the optional OAuth path."""
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token"
            )
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received from GitHub"
            )
        
        user_response = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        )
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user info from GitHub"
            )
        github_user = user_response.json()
    
    github_id = str(github_user["id"])
    github_username = github_user["login"]
    avatar_url = github_user.get("avatar_url")
    
    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()
    if user:
        user.github_username = github_username
        user.github_access_token = access_token
        user.avatar_url = avatar_url
        if not user.username:
            user.username = github_username
    else:
        is_admin = github_username in settings.admin_usernames_list
        user = User(
            github_id=github_id,
            github_username=github_username,
            github_access_token=access_token,
            username=github_username,
            avatar_url=avatar_url,
            is_admin=is_admin
        )
        db.add(user)
        await db.flush()
        await _create_default_limits(db, user.id)
    
    await db.commit()
    await db.refresh(user)
    jwt_token = create_access_token(data={"sub": user.id})
    return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?token={jwt_token}")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user. JWT logout is handled client-side in this prototype."""
    return {"message": "Logged out successfully"}



