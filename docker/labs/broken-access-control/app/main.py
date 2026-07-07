"""
Intentionally vulnerable Broken Access Control (IDOR) target.

/documents/{id} only checks that *some* valid session is present, never that
the session's owner actually owns the requested document - a classic
insecure direct object reference. A student who logs in as an unprivileged
user can walk document IDs and read the admin's private document anyway.
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Broken Access Control Target")

_users = {"alice": "alice123", "bob": "bob123"}
_sessions: dict[str, str] = {}

_documents = {
    1: {"owner": "alice", "content": "Alice's shopping list: eggs, milk."},
    2: {"owner": "bob", "content": "Bob's meeting notes."},
    3: {"owner": "admin", "content": "flag{broken_access_control_idor}"},
}


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><title>Broken Access Control Target</title></head>
      <body>
        <h1>Document Storage</h1>
        <p>Login: <code>POST /login {"username": "alice", "password": "alice123"}</code></p>
        <p>Read a document: <code>GET /documents/1</code></p>
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
    return response


@app.get("/documents/{document_id}")
async def get_document(document_id: int, request: Request):
    session_id = request.cookies.get("session_id")
    username = _sessions.get(session_id or "")

    if not username:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    document = _documents.get(document_id)
    if not document:
        return JSONResponse({"error": "document not found"}, status_code=404)

    # Vulnerable: only checks that *a* session exists, never that this
    # session's user is `document["owner"]` - any logged-in user can read
    # any other user's document by guessing/incrementing the id.
    return JSONResponse({"id": document_id, "content": document["content"]})
