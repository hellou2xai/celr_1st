"""
Username + password auth for the CELR demo.

Endpoints:
    POST /auth/login   { username, password }  -> sets session cookie
    POST /auth/logout                          -> clears cookie
    GET  /auth/me                              -> returns user or 401

Env:
    AUTH_USERNAME   default 'admin'
    AUTH_PASSWORD   default 'admin'
    AUTH_SECRET     HMAC secret for the signed session cookie
    AUTH_SESSION_TTL seconds (default 7 days)

For a real deployment, override the defaults in Render's Environment tab.
The session cookie is signed (HMAC-SHA256) and only set when the password
matches — so even with the trivial demo credentials, a visitor needs to
authenticate before any API or page works.
"""
from __future__ import annotations

import hmac
import hashlib
import hmac as _hmac
import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel

USERNAME = os.environ.get("AUTH_USERNAME", "admin")
PASSWORD = os.environ.get("AUTH_PASSWORD", "admin")
SECRET = os.environ.get("AUTH_SECRET", "dev-insecure-change-in-render").encode()
SESSION_TTL = int(os.environ.get("AUTH_SESSION_TTL", str(7 * 24 * 3600)))

router = APIRouter(prefix="/auth", tags=["auth"])


def _sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def _issue_session(username: str) -> str:
    exp = int(time.time()) + SESSION_TTL
    body = json.dumps({"username": username, "exp": exp})
    return f"{body}|{_sign(body)}"


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


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginPayload, response: Response):
    # Constant-time compare so the failure path doesn't leak timing.
    ok_user = _hmac.compare_digest(req.username.strip(), USERNAME)
    ok_pass = _hmac.compare_digest(req.password, PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(401, "Invalid username or password")
    cookie = _issue_session(USERNAME)
    response.set_cookie(
        "celr_session", cookie,
        max_age=SESSION_TTL, httponly=True, samesite="lax",
        secure=os.environ.get("RENDER", "").lower() == "true",
    )
    return {"ok": True, "username": USERNAME}


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
