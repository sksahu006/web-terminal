"""
Intentionally vulnerable SQL Injection target.

Both endpoints below build SQL by raw string concatenation, mirroring
DVWA's low-security-level SQLi (id parameter and login form).
"""

import sqlite3

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="SQL Injection Target")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT);
        CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, description TEXT);
        CREATE TABLE secrets (id INTEGER PRIMARY KEY, flag TEXT);

        INSERT INTO users (username, password) VALUES ('guest', 'guest123');
        INSERT INTO users (username, password) VALUES ('admin', 'r00t_P@ssw0rd_9f3a');

        INSERT INTO products (name, description) VALUES ('Widget', 'A simple widget.');
        INSERT INTO products (name, description) VALUES ('Gadget', 'A fancy gadget.');

        INSERT INTO secrets (flag) VALUES ('flag{sql_union_extracted}');
        """
    )
    return conn


_db = get_db()


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><title>SQL Injection Target</title></head>
      <body>
        <h1>Mini Shop</h1>
        <p>Login: <code>GET /login?username=&amp;password=</code></p>
        <p>Products: <code>GET /product?id=1</code></p>
      </body>
    </html>
    """


@app.get("/login")
async def login(username: str = Query(default=""), password: str = Query(default="")):
    # Vulnerable: raw string concatenation, no parameterization/escaping.
    query = f"SELECT id, username FROM users WHERE username = '{username}' AND password = '{password}'"
    try:
        cursor = _db.execute(query)
        row = cursor.fetchone()
    except sqlite3.Error as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    if not row:
        return JSONResponse({"authenticated": False})

    user_id, matched_username = row
    result = {"authenticated": True, "user_id": user_id, "username": matched_username}
    if matched_username == "admin":
        result["flag"] = "flag{sql_login_bypassed}"
    return JSONResponse(result)


@app.get("/product")
async def product(id: str = Query(default="1")):
    # Vulnerable: numeric parameter concatenated directly, no quoting/casting,
    # so UNION-based injection against other tables (e.g. secrets) works.
    query = f"SELECT name, description FROM products WHERE id = {id}"
    try:
        cursor = _db.execute(query)
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return JSONResponse(
        {"results": [{"name": name, "description": description} for name, description in rows]}
    )
