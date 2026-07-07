"""
Intentionally vulnerable API Abuse target (mass assignment).

/api/users/{id} accepts an arbitrary JSON patch body and blindly applies
every field the caller sends onto the user record - including `role`, which
should never be client-settable. A logged-in low-privilege user can PATCH
their own record to grant themselves admin, a classic OWASP API Security
Top 10 "mass assignment" flaw.
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="API Abuse Target")

_credentials = {"alice": "alice123", "bob": "bob123"}
_sessions: dict[str, str] = {}

_users = {
    "1": {"id": "1", "username": "alice", "role": "user"},
    "2": {"id": "2", "username": "bob", "role": "user"},
}
_username_to_id = {"alice": "1", "bob": "2"}


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><title>API Abuse Target</title></head>
      <body>
        <h1>User Profile API</h1>
        <p>Login: <code>POST /login {"username": "alice", "password": "alice123"}</code></p>
        <p>Update profile: <code>PATCH /api/users/1 {"bio": "..."}</code></p>
        <p>Admin-only: <code>GET /api/flag</code></p>
      </body>
    </html>
    """


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
async def login(payload: LoginRequest):
    if _credentials.get(payload.username) != payload.password:
        return JSONResponse({"authenticated": False}, status_code=401)

    session_id = str(uuid.uuid4())
    _sessions[session_id] = payload.username
    response = JSONResponse({"authenticated": True, "username": payload.username})
    response.set_cookie("session_id", session_id, httponly=False)
    return response


def _current_username(request: Request) -> str | None:
    session_id = request.cookies.get("session_id")
    return _sessions.get(session_id or "")


@app.patch("/api/users/{user_id}")
async def update_user(user_id: str, patch: dict, request: Request):
    username = _current_username(request)
    if not username:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    if _username_to_id.get(username) != user_id:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    user = _users.get(user_id)
    if not user:
        return JSONResponse({"error": "not found"}, status_code=404)

    # Vulnerable: every field in the client's JSON body is applied directly
    # to the stored record, with no whitelist - `role` was never meant to be
    # client-settable, but nothing here stops it.
    user.update(patch)

    return JSONResponse({"updated": True, "user": user})


@app.get("/api/flag")
async def get_flag(request: Request):
    username = _current_username(request)
    if not username:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    user_id = _username_to_id.get(username)
    user = _users.get(user_id or "")
    if not user or user.get("role") != "admin":
        return JSONResponse({"error": "admin role required"}, status_code=403)

    return JSONResponse({"flag": "flag{api_mass_assignment_privilege_escalation}"})
