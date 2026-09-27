import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.db import get_db

ROLES = {"viewer": 0, "editor": 1, "owner": 2}


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    workspace_id: str
    role: str
    mode: str


def local_context() -> AuthContext:
    return AuthContext(user_id="local-user", workspace_id="local-workspace", role="owner", mode="local")


def require_role(actual: str, required: str) -> HTTPException | None:
    if ROLES.get(actual, -1) < ROLES[required]:
        return HTTPException(status_code=403, detail="FORBIDDEN")
    return None


def mint_promptdiff_jwt(user_id: str, workspace_id: str, role: str, lifetime_seconds: int = 900) -> str:
    settings = get_settings()
    if not settings.promptdiff_jwt_private_key:
        raise RuntimeError("PROMPTDIFF_JWT_PRIVATE_KEY is required")
    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.promptdiff_jwt_issuer,
            "aud": settings.promptdiff_jwt_audience,
            "sub": user_id,
            "workspace_id": workspace_id,
            "role": role,
            "iat": now,
            "nbf": now,
            "exp": now + lifetime_seconds,
            "jti": str(uuid.uuid4()),
        },
        settings.promptdiff_jwt_private_key,
        algorithm="EdDSA",
        headers={"kid": settings.promptdiff_jwt_key_id, "typ": "JWT"},
    )


def validate_promptdiff_jwt(token: str) -> AuthContext:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "EdDSA" or header.get("kid") != settings.promptdiff_jwt_key_id:
            raise HTTPException(status_code=401, detail="INVALID_TOKEN")
        claims = jwt.decode(
            token,
            settings.promptdiff_jwt_public_key,
            algorithms=["EdDSA"],
            issuer=settings.promptdiff_jwt_issuer,
            audience=settings.promptdiff_jwt_audience,
            leeway=30,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN") from exc
    if not claims.get("sub") or not claims.get("workspace_id") or claims.get("role") not in ROLES:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")
    return AuthContext(user_id=claims["sub"], workspace_id=claims["workspace_id"], role=claims["role"], mode="hosted")


@lru_cache
def jwks_client() -> jwt.PyJWKClient:
    settings = get_settings()
    if not settings.neon_auth_jwks_url:
        raise HTTPException(status_code=503, detail="NEON_AUTH_NOT_CONFIGURED")
    return jwt.PyJWKClient(settings.neon_auth_jwks_url, cache_jwk_set=True, lifespan=300, timeout=5)


def validate_neon_jwt(token: str) -> dict:
    settings = get_settings()
    if not settings.neon_auth_audience:
        raise HTTPException(status_code=503, detail="NEON_AUTH_NOT_CONFIGURED")
    try:
        signing_key = jwks_client().get_signing_key_from_jwt(token).key
        kwargs = {
            "algorithms": ["RS256", "ES256", "EdDSA"],
            "audience": settings.neon_auth_audience,
        }
        if settings.neon_auth_base_url:
            kwargs["issuer"] = settings.neon_auth_base_url
        claims = jwt.decode(token, signing_key, **kwargs)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="INVALID_NEON_TOKEN") from exc
    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="INVALID_NEON_TOKEN")
    return claims


def current_context(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> AuthContext:
    settings = get_settings()
    if settings.promptdiff_mode != "hosted":
        return local_context()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    context = validate_promptdiff_jwt(authorization.split(" ", 1)[1])
    member = db.get(models.WorkspaceMember, (context.workspace_id, context.user_id))
    if member is None or member.role != context.role:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    return context
