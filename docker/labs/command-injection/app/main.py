"""
Intentionally vulnerable Command Injection target.

/ping shells out with unsanitized user input, mirroring DVWA's low-security-level
`shell_exec('ping ' . $target)` flaw.
"""

import subprocess

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Command Injection Target")


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><meta charset="utf-8" /><title>Command Injection Target</title></head>
      <body>
        <h1>Network Ping Tool</h1>
        <p><code>GET /ping?host=127.0.0.1</code></p>
      </body>
    </html>
    """


@app.get("/ping")
async def ping(host: str = Query(default="127.0.0.1")):
    # Vulnerable: user input concatenated directly into a shell command.
    command = f"ping -c 1 -W 1 {host}"
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return JSONResponse({"command": command, "output": result.stdout + result.stderr})
