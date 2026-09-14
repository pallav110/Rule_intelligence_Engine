"""Auth request/response schemas (Spec §5.1, §10.1)."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials for POST /v1/auth/token."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")
    workspace_id: str = Field(..., description="Workspace to authenticate against")


class TokenResponse(BaseModel):
    """Signed access token returned after successful login."""

    access_token: str = Field(..., description="HS256-signed JWT access token")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")
    role: str = Field(..., description="Workspace role granted (business_user|reviewer|administrator)")
    workspace_id: str = Field(..., description="Workspace scoped to this token")