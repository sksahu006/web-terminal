"""
Authentication router handling GitHub OAuth flow and JWT tokens.
"""

from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import get_settings
from ..core.database import get_db
from ..core.security import create_access_token, get_current_user
from ..models.user import User
from ..models.user_limits import UserLimits
from ..schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

# GitHub OAuth URLs
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@router.get("/github")
async def github_login():
    """
    Redirect user to GitHub OAuth authorization page.
    """
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "read:user user:email repo",
        "state": "random_state_string",  # TODO: Implement proper CSRF protection
    }
    
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GITHUB_AUTHORIZE_URL}?{query_string}")


@router.get("/github/callback")
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle GitHub OAuth callback.
    Exchange code for access token, fetch user info, create/update user.
    """
    # Exchange code for access token
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
        
        # Fetch user information from GitHub
        user_response = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
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
    
    # Check if user exists
    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()
    
    if user:
        # Update existing user
        user.github_username = github_username
        user.github_access_token = access_token
        user.avatar_url = avatar_url
    else:
        # Create new user
        is_admin = github_username in settings.admin_usernames_list
        user = User(
            github_id=github_id,
            github_username=github_username,
            github_access_token=access_token,
            avatar_url=avatar_url,
            is_admin=is_admin
        )
        db.add(user)
        await db.flush()
        
        # Create default limits for new user
        default_limits = UserLimits(user_id=user.id)
        db.add(default_limits)
    
    await db.commit()
    
    # Create JWT token
    jwt_token = create_access_token(data={"sub": user.id})
    
    # Redirect to frontend with token
    redirect_url = f"{settings.frontend_url}/auth/callback?token={jwt_token}"
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.
    """
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user. In a stateless JWT system, this is mainly for client-side cleanup.
    Could be extended to add token to a blacklist.
    """
    return {"message": "Logged out successfully"}
