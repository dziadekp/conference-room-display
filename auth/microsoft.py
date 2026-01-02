"""
Microsoft 365 Calendar OAuth integration.
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import msal

from database import get_db, CalendarToken

router = APIRouter()

# Microsoft OAuth configuration
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")  # 'common' for multi-tenant
MICROSOFT_SCOPES = [
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/User.Read",
]

AUTHORITY = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}"


def get_msal_app(redirect_uri: str = None) -> msal.ConfidentialClientApplication:
    """Create MSAL application."""
    if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Microsoft OAuth not configured. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET."
        )

    return msal.ConfidentialClientApplication(
        MICROSOFT_CLIENT_ID,
        authority=AUTHORITY,
        client_credential=MICROSOFT_CLIENT_SECRET,
    )


@router.get("/login")
async def microsoft_login(request: Request):
    """Initiate Microsoft OAuth flow."""
    redirect_uri = str(request.url_for("microsoft_callback"))
    msal_app = get_msal_app(redirect_uri)

    auth_url = msal_app.get_authorization_request_url(
        scopes=MICROSOFT_SCOPES,
        redirect_uri=redirect_uri,
        prompt="select_account",
    )

    return RedirectResponse(auth_url)


@router.get("/callback")
async def microsoft_callback(
    request: Request,
    code: str = None,
    error: str = None,
    error_description: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Microsoft OAuth callback."""
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error} - {error_description}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    redirect_uri = str(request.url_for("microsoft_callback"))
    msal_app = get_msal_app(redirect_uri)

    try:
        result = msal_app.acquire_token_by_authorization_code(
            code=code,
            scopes=MICROSOFT_SCOPES,
            redirect_uri=redirect_uri,
        )

        if "error" in result:
            raise HTTPException(
                status_code=500,
                detail=f"Token error: {result.get('error_description', result.get('error'))}"
            )

        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        expires_in = result.get("expires_in", 3600)

        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Check if we already have a Microsoft token
        db_result = await db.execute(
            select(CalendarToken).where(CalendarToken.provider == "microsoft")
        )
        existing_token = db_result.scalar_one_or_none()

        if existing_token:
            existing_token.access_token = access_token
            existing_token.refresh_token = refresh_token or existing_token.refresh_token
            existing_token.expires_at = expires_at
            existing_token.scope = " ".join(MICROSOFT_SCOPES)
            existing_token.updated_at = datetime.utcnow()
        else:
            token = CalendarToken(
                provider="microsoft",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=" ".join(MICROSOFT_SCOPES),
            )
            db.add(token)

        await db.commit()

        return RedirectResponse("/setup?microsoft=connected")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange token: {str(e)}")


async def get_microsoft_token(db: AsyncSession) -> str | None:
    """Get valid Microsoft access token, refreshing if necessary."""
    result = await db.execute(
        select(CalendarToken).where(CalendarToken.provider == "microsoft")
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        return None

    # Check if token needs refresh
    if token_record.expires_at and datetime.utcnow() >= token_record.expires_at:
        if token_record.refresh_token:
            try:
                msal_app = get_msal_app()
                result = msal_app.acquire_token_by_refresh_token(
                    token_record.refresh_token,
                    scopes=MICROSOFT_SCOPES,
                )

                if "error" in result:
                    return None

                token_record.access_token = result["access_token"]
                token_record.refresh_token = result.get("refresh_token", token_record.refresh_token)
                expires_in = result.get("expires_in", 3600)
                token_record.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                token_record.updated_at = datetime.utcnow()
                await db.commit()

            except Exception:
                return None
        else:
            return None

    return token_record.access_token
