"""
Google Calendar OAuth integration.
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from database import get_db, CalendarToken

router = APIRouter()

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",  # Full calendar access (list, create, modify)
]


def get_google_flow(redirect_uri: str) -> Flow:
    """Create Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )

    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


@router.get("/login")
async def google_login(request: Request):
    """Initiate Google OAuth flow."""
    redirect_uri = str(request.url_for("google_callback"))
    flow = get_google_flow(redirect_uri)

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",  # Force re-consent to get fresh scopes
    )

    # Store state in session (simple approach for demo)
    # In production, use secure session management
    return RedirectResponse(authorization_url)


@router.get("/callback")
async def google_callback(
    request: Request,
    code: str = None,
    error: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Google OAuth callback."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    redirect_uri = str(request.url_for("google_callback"))
    flow = get_google_flow(redirect_uri)

    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Calculate expiry
        expires_at = None
        if credentials.expiry:
            expires_at = credentials.expiry

        # Check if we already have a Google token
        result = await db.execute(
            select(CalendarToken).where(CalendarToken.provider == "google")
        )
        existing_token = result.scalar_one_or_none()

        if existing_token:
            # Update existing token
            existing_token.access_token = credentials.token
            existing_token.refresh_token = credentials.refresh_token or existing_token.refresh_token
            existing_token.expires_at = expires_at
            existing_token.scope = " ".join(credentials.scopes) if credentials.scopes else None
            existing_token.updated_at = datetime.utcnow()
        else:
            # Create new token
            token = CalendarToken(
                provider="google",
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=expires_at,
                scope=" ".join(credentials.scopes) if credentials.scopes else None,
            )
            db.add(token)

        await db.commit()

        return RedirectResponse("/setup?google=connected")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange token: {str(e)}")


async def get_google_credentials(db: AsyncSession) -> Credentials | None:
    """Get valid Google credentials, refreshing if necessary."""
    result = await db.execute(
        select(CalendarToken).where(CalendarToken.provider == "google")
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        return None

    credentials = Credentials(
        token=token_record.access_token,
        refresh_token=token_record.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_SCOPES,
    )

    # Check if token needs refresh
    if token_record.expires_at and datetime.utcnow() >= token_record.expires_at:
        if credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request as GoogleRequest
                credentials.refresh(GoogleRequest())

                # Update stored token
                token_record.access_token = credentials.token
                token_record.expires_at = credentials.expiry
                token_record.updated_at = datetime.utcnow()
                await db.commit()
            except Exception:
                return None
        else:
            return None

    return credentials
