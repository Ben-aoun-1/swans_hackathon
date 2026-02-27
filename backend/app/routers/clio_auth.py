from fastapi import APIRouter

router = APIRouter(prefix="/api/clio", tags=["clio-auth"])


@router.get("/auth")
async def clio_auth():
    """Redirect to Clio OAuth authorization page."""
    # TODO: Build Clio OAuth authorize URL and redirect
    return {"status": "not_implemented"}


@router.get("/callback")
async def clio_callback(code: str | None = None):
    """Handle Clio OAuth callback and exchange code for tokens."""
    # TODO: Exchange code for access/refresh tokens
    return {"status": "not_implemented", "code": code}
