"""
Magic-link auth for the CELR demo.

Flow:
    POST /auth/request { email }       -> generates one-time token, emails it
    POST /auth/verify  { email, token } -> sets a session cookie
    POST /auth/logout                   -> clears the cookie
    GET  /auth/me                       -> returns the active user or 401

In dev (no AUTH_EMAIL_PROVIDER configured) the token is returned in the
response body so a developer can verify locally without an email key.

Env:
    AUTH_ALLOWED_EMAILS    Comma-separated allowlist (exact match)
    AUTH_ALLOWED_DOMAINS   Comma-separated domains (e.g. "u2xai.com")
    AUTH_SECRET            HMAC secret for signing tokens / cookies
    AUTH_TOKEN_TTL         Seconds (default 900 = 15 min) for magic links
    AUTH_SESSION_TTL       Seconds (default 7 days) for the session cookie
    AUTH_EMAIL_PROVIDER    "resend" | "none" (none = dev mode, returns token)
    RESEND_API_KEY         Required if AUTH_EMAIL_PROVIDER=resend
    RESEND_FROM            From-address for outbound mail
    PUBLIC_URL             Used to build the magic-link URL in the email
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

SECRET = os.environ.get("AUTH_SECRET", "dev-insecure-change-in-render").encode()
TOKEN_TTL = int(os.environ.get("AUTH_TOKEN_TTL", "900"))
SESSION_TTL = int(os.environ.get("AUTH_SESSION_TTL", str(7 * 24 * 3600)))
ALLOWED_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("AUTH_ALLOWED_EMAILS", "hello@u2xai.com").split(",")
    if e.strip()
}
ALLOWED_DOMAINS = {
    d.strip().lower().lstrip("@")
    for d in os.environ.get("AUTH_ALLOWED_DOMAINS", "").split(",")
    if d.strip()
}
PROVIDER = os.environ.get("AUTH_EMAIL_PROVIDER", "none").lower()
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "CELR <noreply@example.com>")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "")

router = APIRouter(prefix="/auth", tags=["auth"])

# Stores issued magic-link tokens in memory (single-worker assumption).
# A production deploy across multiple workers would back this with Postgres
# or Redis. For a starter Render plan with 1 worker it's fine.
_pending: dict[str, tuple[str, float]] = {}  # token -> (email, expiry)


def _allow(email: str) -> bool:
    e = email.lower().strip()
    if e in ALLOWED_EMAILS:
        return True
    domain = e.split("@", 1)[1] if "@" in e else ""
    return domain in ALLOWED_DOMAINS


def _sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def _issue_session(email: str) -> str:
    exp = int(time.time()) + SESSION_TTL
    body = json.dumps({"email": email, "exp": exp})
    sig = _sign(body)
    return f"{body}|{sig}"


def _read_session(cookie: Optional[str]) -> Optional[dict]:
    if not cookie or "|" not in cookie:
        return None
    body, sig = cookie.rsplit("|", 1)
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


def current_user(request: Request) -> dict:
    user = _read_session(request.cookies.get("celr_session"))
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def _send_email(to: str, token: str) -> bool:
    """Returns True if dispatched; False to indicate dev-mode (token returned)."""
    if PROVIDER != "resend" or not RESEND_KEY:
        return False
    link = f"{PUBLIC_URL or ''}/login?token={token}&email={to}".lstrip("/")
    body_html = (
        f"<p>Click to sign in to CELR Procurement:</p>"
        f"<p><a href='{link}'>{link}</a></p>"
        f"<p>Or paste this code: <code>{token}</code></p>"
        f"<p>This link expires in {TOKEN_TTL // 60} minutes.</p>"
    )
    try:
        import requests  # type: ignore
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}"},
            json={"from": RESEND_FROM, "to": [to],
                  "subject": "CELR Procurement sign-in",
                  "html": body_html},
            timeout=10,
        )
        return r.ok
    except Exception:
        return False


class RequestLink(BaseModel):
    email: EmailStr


@router.post("/request")
def request_link(req: RequestLink):
    email = req.email.lower().strip()
    if not _allow(email):
        raise HTTPException(403, "This address is not on the allowlist.")
    token = secrets.token_urlsafe(24)
    _pending[token] = (email, time.time() + TOKEN_TTL)
    sent = _send_email(email, token)
    if sent:
        return {"ok": True, "sent": True}
    # Dev mode — surface the token so a local dev can paste it back.
    return {"ok": True, "sent": False, "dev_token": token,
            "note": "AUTH_EMAIL_PROVIDER is not configured; token returned for dev."}


class Verify(BaseModel):
    email: EmailStr
    token: str


@router.post("/verify")
def verify(req: Verify, response: Response):
    email = req.email.lower().strip()
    entry = _pending.get(req.token)
    if not entry or entry[0] != email:
        raise HTTPException(400, "Invalid or expired token")
    if entry[1] < time.time():
        _pending.pop(req.token, None)
        raise HTTPException(400, "Token expired")
    _pending.pop(req.token, None)
    cookie = _issue_session(email)
    response.set_cookie(
        "celr_session", cookie,
        max_age=SESSION_TTL, httponly=True, samesite="lax",
        secure=os.environ.get("RENDER", "").lower() == "true",
    )
    return {"ok": True, "email": email}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("celr_session")
    return {"ok": True}


@router.get("/me")
def me(celr_session: Optional[str] = Cookie(default=None)):
    user = _read_session(celr_session)
    if not user:
        raise HTTPException(401, "Not signed in")
    return user
