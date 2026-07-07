"""
Intentionally vulnerable CSRF target.

/change-password accepts a GET request and changes the *currently logged-in*
user's password using only the session cookie for authorization - no CSRF
token, no re-entry of the current password, mirroring DVWA's low-security-level
CSRF module.

Since the lab has no real browser to simulate a victim clicking a malicious
link, /simulate-admin-click plays the part of "the admin is already logged in
and clicks your link" by replaying a GET request against this same server
using a pre-authenticated admin session - exactly the trust a real CSRF attack
abuses.
"""

import uuid

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="CSRF Target")

_users = {"admin": "admin_original_pw", "guest": "guest123"}
_sessions: dict[str, str] = {}

_ADMIN_SESSION = "admin-preauth-session"
_sessions[_ADMIN_SESSION] = "admin"


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><title>CSRF Target</title></head>
      <body>
        <h1>Account Settings</h1>
        <p>Login: <code>POST /login {"username": "...", "password": "..."}</code></p>
        <p>Change password (no CSRF token!): <code>GET /change-password?new_password=...</code></p>
        <p>Get the admin to click your link: <code>POST /simulate-admin-click {"url": "..."}</code></p>
      </body>
    </html>
    """


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
async def login(payload: LoginRequest):
    if _users.get(payload.username) != payload.password:
        return JSONResponse({"authenticated": False}, status_code=401)

    session_id = str(uuid.uuid4())
    _sessions[session_id] = payload.username
    response = JSONResponse({"authenticated": True, "username": payload.username})
    response.set_cookie("session_id", session_id, httponly=False)

    if payload.username == "admin":
        response.headers["X-Flag"] = "flag{csrf_password_changed}"

    return response


@app.get("/change-password")
async def change_password(request: Request, new_password: str = Query(...)):
    session_id = request.cookies.get("session_id")
    username = _sessions.get(session_id or "")

    if not username:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    # Vulnerable: state-changing action performed on a GET request, guarded
    # only by the session cookie - no anti-CSRF token verification, no
    # re-confirmation of the current password.
    _users[username] = new_password
    return JSONResponse({"changed": True, "username": username})


class SimulateClickRequest(BaseModel):
    url: str


@app.post("/simulate-admin-click")
async def simulate_admin_click(payload: SimulateClickRequest):
    # Represents an already-authenticated admin loading a link an attacker
    # sent them - their browser automatically attaches their session cookie,
    # regardless of which site served the link.
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        cookies={"session_id": _ADMIN_SESSION},
        timeout=5,
    ) as client:
        response = await client.get(payload.url)

    return JSONResponse(
        {
            "admin_clicked": True,
            "status_code": response.status_code,
            "body": response.text,
        }
    )
