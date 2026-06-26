"""
Small intentionally vulnerable target for the Web Basics room.
"""

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="Web Basics Target")


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Web Basics Target</title>
      </head>
      <body>
        <h1>Web Basics Target</h1>
        <p>The attacker terminal can reach this private target through TARGET_URL.</p>
        <p>Homepage flag: <code>flag{web_target_reachable}</code></p>
        <p>Hint: debug endpoints often reveal more than they should.</p>
      </body>
    </html>
    """


@app.get("/debug")
async def debug(show: str = Query(default="")) -> dict[str, str | bool]:
    if show == "flag":
        return {"debug": True, "flag": "flag{debug_endpoint_found}"}

    return {"debug": True, "hint": "Try show=flag"}
