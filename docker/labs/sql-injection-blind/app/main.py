"""
Intentionally vulnerable Blind SQL Injection target.

Unlike the regular SQL Injection lab, these endpoints never reflect query
results back to the caller - only a boolean ("Exists"/"Not Found") or a
timing difference. Students must extract the flag one character at a time
using boolean- and time-based oracles, exactly like DVWA's sqli_blind module
(and real-world blind SQLi exploitation with tools like sqlmap).
"""

import sqlite3
import time

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Blind SQL Injection Target")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    # SQLite has no native SLEEP(); register one so time-based payloads
    # (mirroring MySQL's SLEEP()) work the same way DVWA's blind lab expects.
    conn.create_function("sleep", 1, lambda seconds: time.sleep(min(float(seconds), 5)) or 0)
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
        CREATE TABLE secrets (id INTEGER PRIMARY KEY, flag_bool TEXT, flag_time TEXT);

        INSERT INTO users (username) VALUES ('guest');
        INSERT INTO users (username) VALUES ('admin');

        INSERT INTO secrets (flag_bool, flag_time)
        VALUES ('flag{blind_boolean_extracted}', 'flag{blind_time_extracted}');
        """
    )
    return conn


_db = get_db()


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><title>Blind SQL Injection Target</title></head>
      <body>
        <h1>User Directory (Blind)</h1>
        <p>Boolean oracle: <code>GET /profile?id=1</code> (returns only Exists/Not Found)</p>
        <p>Time oracle: <code>GET /profile-time?id=1</code> (response time reveals truth)</p>
      </body>
    </html>
    """


@app.get("/profile")
async def profile(id: str = Query(default="1")):
    # Vulnerable: numeric parameter concatenated directly, no quoting/casting.
    # The response never reveals data - only whether a row matched - forcing
    # boolean-based blind extraction via subqueries against `secrets`.
    query = f"SELECT username FROM users WHERE id = {id}"
    try:
        cursor = _db.execute(query)
        row = cursor.fetchone()
    except sqlite3.Error:
        return JSONResponse({"found": False})

    return JSONResponse({"found": row is not None})


@app.get("/profile-time")
async def profile_time(id: str = Query(default="1")):
    # Vulnerable the same way, but with no observable output difference at
    # all - only response latency reveals whether the injected condition
    # was true, via the registered sleep() SQL function.
    query = f"SELECT username FROM users WHERE id = {id}"
    started = time.monotonic()
    try:
        _db.execute(query).fetchone()
    except sqlite3.Error:
        pass
    elapsed = time.monotonic() - started

    return JSONResponse({"elapsed_seconds": round(elapsed, 2)})
