"""
Prototype lab seed data for fresh SQLite databases.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.lab import Challenge, LabAccessMode, LabTemplate, Room


async def _room_exists(db: AsyncSession, slug: str) -> bool:
    result = await db.execute(select(Room.id).where(Room.slug == slug))
    return result.scalar_one_or_none() is not None


async def seed_default_labs(db: AsyncSession) -> None:
    """Create starter rooms once, without blocking future seed additions."""
    changed = False

    # Dynamic correction for existing rooms
    # Ensure existing web-basics template has the correct split image name
    result_web = await db.execute(
        select(Room)
        .options(selectinload(Room.template))
        .where(Room.slug == "web-basics")
    )
    room_web = result_web.scalar_one_or_none()
    if room_web and room_web.template:
        if room_web.template.image != "workspace-dev:latest|web-basics-target:latest":
            room_web.template.image = "workspace-dev:latest|web-basics-target:latest"
            room_web.template.access_mode = LabAccessMode.WEB_TARGET.value
            room_web.template.default_port = 7681
            changed = True

    # Ensure existing browser-desktop template has the correct VNC browser image
    result_browser = await db.execute(
        select(Room)
        .options(selectinload(Room.template), selectinload(Room.challenges))
        .where(Room.slug == "browser-desktop")
    )
    room_browser = result_browser.scalar_one_or_none()
    if room_browser and room_browser.template:
        if room_browser.template.image != "mrcolorrain/vnc-browser:alpine":
            room_browser.template.image = "mrcolorrain/vnc-browser:alpine"
            room_browser.template.default_port = 6080
            changed = True
        # Xvnc + Firefox + Fluxbox + websockify need meaningfully more than the
        # 0.25 CPU / 256MB floor a plain bash shell needs - undersizing this
        # one lets it start and idle fine, then get OOM-killed under real use.
        if room_browser.template.attacker_cpu < 1.0 or room_browser.template.attacker_memory < 1024:
            room_browser.template.attacker_cpu = 1.0
            room_browser.template.attacker_memory = 1024
            changed = True
        for challenge in room_browser.challenges:
            if "money4band" not in challenge.prompt:
                challenge.prompt = (
                    "Open the desktop in your workspace dashboard. If prompted for a VNC password, "
                    "enter `money4band` (this image's built-in default). Navigate the browser to the "
                    "target and submit the flag."
                )
                changed = True

    if not await _room_exists(db, "linux-basics"):
        template = LabTemplate(
            name="Terminal Basics",
            access_mode=LabAccessMode.TERMINAL.value,
            image="workspace-dev:latest",
            default_port=7681,
        )
        room = Room(
            slug="linux-basics",
            title="Linux Basics",
            difficulty="easy",
            description="A first terminal-only room for practicing Linux navigation and flag discovery.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Read the Welcome Flag",
                prompt="Start the room and find the flag in the workspace.",
                flag="flag{linux_basics_started}",
                points=10,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "web-basics"):
        template = LabTemplate(
            name="Web Target Basics",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|web-basics-target:latest",
            default_port=7681,
        )
        room = Room(
            slug="web-basics",
            title="Web Basics",
            difficulty="easy",
            description="Attack a small intentionally vulnerable web target from your terminal lab.",
            is_published=True,
            template=template,
        )
        room.challenges.extend(
            [
                Challenge(
                    title="Read the Target Homepage",
                    prompt="Start the room, open the terminal, run `curl $TARGET_URL`, and submit the flag shown on the homepage.",
                    flag="flag{web_target_reachable}",
                    points=10,
                    sort_order=1,
                ),
                Challenge(
                    title="Find the Debug Flag",
                    prompt="Query `$TARGET_URL/debug?show=flag` and submit the debug flag.",
                    flag="flag{debug_endpoint_found}",
                    points=15,
                    sort_order=2,
                ),
            ]
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "kali-terminal"):
        template = LabTemplate(
            name="Kali Terminal",
            access_mode=LabAccessMode.TERMINAL.value,
            image="kali-terminal:latest",
            default_port=7681,
        )
        room = Room(
            slug="kali-terminal",
            title="Kali Linux Terminal",
            difficulty="medium",
            description="A Kali Linux environment with nmap, netcat, curl, python3, and standard recon tools.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Scan the Target",
                prompt="Run `nmap -sn 172.0.0.0/24` and find the live host. Submit the IP as the flag.",
                flag="flag{kali_recon_complete}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "browser-desktop"):
        template = LabTemplate(
            name="Browser Desktop",
            # We use TERMINAL mode because the backend treats it as a single container
            # serving HTTP (noVNC browser) on the exposed port, exactly like ttyd does.
            access_mode=LabAccessMode.TERMINAL.value,
            image="mrcolorrain/vnc-browser:alpine",
            default_port=6080, # noVNC port
            attacker_cpu=1.0,
            attacker_memory=1024,
        )
        room = Room(
            slug="browser-desktop",
            title="GUI Desktop Lab",
            difficulty="medium",
            description="A lightweight Chromium browser environment accessed directly inside your dashboard. Powered by Alpine Linux.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Browse the Web",
                prompt=(
                    "Open the desktop in your workspace dashboard. If prompted for a VNC password, "
                    "enter `money4band` (this image's built-in default). Navigate the browser to the "
                    "target and submit the flag."
                ),
                flag="flag{gui_desktop_active}",
                points=30,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "sql-injection"):
        template = LabTemplate(
            name="SQL Injection Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|sql-injection-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="sql-injection",
            title="SQL Injection",
            difficulty="medium",
            description="Bypass a login form and extract hidden data from a vulnerable product lookup.",
            is_published=True,
            template=template,
        )
        room.challenges.extend(
            [
                Challenge(
                    title="Bypass the Login",
                    prompt=(
                        "Query `$TARGET_URL/login?username=&password=` with a crafted "
                        "username to log in as admin without knowing the password."
                    ),
                    flag="flag{sql_login_bypassed}",
                    points=20,
                    sort_order=1,
                ),
                Challenge(
                    title="Extract the Hidden Flag",
                    prompt=(
                        "Query `$TARGET_URL/product?id=` with a UNION-based payload to "
                        "read the flag out of the `secrets` table."
                    ),
                    flag="flag{sql_union_extracted}",
                    points=25,
                    sort_order=2,
                ),
            ]
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "command-injection"):
        template = LabTemplate(
            name="Command Injection Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|command-injection-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="command-injection",
            title="Command Injection",
            difficulty="medium",
            description="Chain a shell command onto a ping tool that concatenates unsanitized input.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Read the Flag File",
                prompt=(
                    "Query `$TARGET_URL/ping?host=` with a chained shell command to "
                    "read `/flag.txt` on the target."
                ),
                flag="flag{command_injection_pwned}",
                points=25,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "xss-reflected"):
        template = LabTemplate(
            name="Reflected XSS Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|xss-reflected-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="xss-reflected",
            title="Reflected XSS",
            difficulty="easy",
            description="Craft a script payload that survives unescaped into the page the admin bot loads.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Get the Admin to Run Your Script",
                prompt=(
                    "POST a crafted `<script>` payload to `$TARGET_URL/report-to-admin` "
                    "so it reaches the admin bot's page unescaped."
                ),
                flag="flag{reflected_xss_confirmed}",
                points=15,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "xss-stored"):
        template = LabTemplate(
            name="Stored XSS Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|xss-stored-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="xss-stored",
            title="Stored XSS",
            difficulty="medium",
            description="Plant a persistent script in a guestbook that fires when the admin views it.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Persist a Script in the Guestbook",
                prompt=(
                    "POST a comment containing a `<script>` payload to `$TARGET_URL/comment`, "
                    "then check `$TARGET_URL/admin-check`."
                ),
                flag="flag{stored_xss_admin_pwned}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "file-upload"):
        template = LabTemplate(
            name="File Upload Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|file-upload-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="file-upload",
            title="Unrestricted File Upload",
            difficulty="hard",
            description="Upload an unchecked script to a file host and execute it to read the target's flag.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Upload and Execute a Payload",
                prompt=(
                    "Upload a `.py` file to `$TARGET_URL/upload` that prints the contents "
                    "of `/flag.txt`, then trigger it via `$TARGET_URL/run/<filename>`."
                ),
                flag="flag{unrestricted_upload_rce}",
                points=30,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "sql-injection-blind"):
        template = LabTemplate(
            name="Blind SQL Injection Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|sql-injection-blind-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="sql-injection-blind",
            title="SQL Injection (Blind)",
            difficulty="hard",
            description="Extract two hidden flags using boolean- and time-based blind SQL injection oracles.",
            is_published=True,
            template=template,
        )
        room.challenges.extend(
            [
                Challenge(
                    title="Boolean-Based Extraction",
                    prompt=(
                        "Query `$TARGET_URL/profile?id=` with boolean subquery payloads "
                        "against the `secrets` table to extract `flag_bool` one character at a time."
                    ),
                    flag="flag{blind_boolean_extracted}",
                    points=30,
                    sort_order=1,
                ),
                Challenge(
                    title="Time-Based Extraction",
                    prompt=(
                        "Query `$TARGET_URL/profile-time?id=` with `sleep()` payloads "
                        "against the `secrets` table to extract `flag_time` via response timing."
                    ),
                    flag="flag{blind_time_extracted}",
                    points=30,
                    sort_order=2,
                ),
            ]
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "csrf"):
        template = LabTemplate(
            name="CSRF Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|csrf-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="csrf",
            title="Cross-Site Request Forgery",
            difficulty="medium",
            description="Get the admin to unknowingly change their own password, then log in as them.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Hijack the Admin's Password",
                prompt=(
                    "POST a crafted URL to `$TARGET_URL/simulate-admin-click` that hits "
                    "`/change-password?new_password=...` with no CSRF token, then log in as admin "
                    "with your chosen password via `$TARGET_URL/login`."
                ),
                flag="flag{csrf_password_changed}",
                points=25,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "broken-access-control"):
        template = LabTemplate(
            name="Broken Access Control Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|broken-access-control-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="broken-access-control",
            title="Broken Access Control",
            difficulty="easy",
            description="Log in as a low-privilege user and read another user's private document by ID.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Read the Admin's Document",
                prompt=(
                    "Log in via `$TARGET_URL/login` as alice or bob, then request "
                    "`$TARGET_URL/documents/3` (the admin's document) directly."
                ),
                flag="flag{broken_access_control_idor}",
                points=15,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "weak-session-ids"):
        template = LabTemplate(
            name="Weak Session IDs Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|weak-session-ids-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="weak-session-ids",
            title="Weak Session IDs",
            difficulty="easy",
            description="Guess a predictable, sequential session id to hijack the admin's session.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Hijack the Admin Session",
                prompt=(
                    "The admin logged in before you. Guess their sequential session id and "
                    "query `$TARGET_URL/flag` with `Cookie: session=<id>`."
                ),
                flag="flag{weak_session_hijacked}",
                points=15,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "open-redirect"):
        template = LabTemplate(
            name="Open Redirect Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|open-redirect-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="open-redirect",
            title="Open Redirect",
            difficulty="easy",
            description="Prove the redirect endpoint will forward users to any off-site URL unchecked.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Redirect Off-Site Unchecked",
                prompt=(
                    "Query `$TARGET_URL/redirect?url=` with an absolute external URL and "
                    "read the `X-Redirect-Flag` response header."
                ),
                flag="flag{open_redirect_exploited}",
                points=10,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "file-inclusion"):
        template = LabTemplate(
            name="File Inclusion Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|file-inclusion-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="file-inclusion",
            title="Local File Inclusion",
            difficulty="medium",
            description="Escape a help-page directory with path traversal to read a file outside it.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Traverse Outside the Pages Directory",
                prompt=(
                    "Query `$TARGET_URL/page?file=` with a `../` traversal payload to read "
                    "`secret.txt` outside the `pages/` directory."
                ),
                flag="flag{local_file_included}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "xss-dom"):
        template = LabTemplate(
            name="DOM XSS Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|xss-dom-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="xss-dom",
            title="DOM-Based XSS",
            difficulty="medium",
            description="Craft a URL fragment payload that a vulnerable client-side script writes unescaped into the DOM.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Exploit the Client-Side Sink",
                prompt=(
                    "Inspect `$TARGET_URL/welcome`'s inline script, craft a `<script>`-bearing "
                    "hash payload, and confirm it via `$TARGET_URL/admin-check-dom?hash=`."
                ),
                flag="flag{dom_xss_confirmed}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "csp-bypass"):
        template = LabTemplate(
            name="CSP Bypass Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|csp-bypass-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="csp-bypass",
            title="Content-Security-Policy Bypass",
            difficulty="medium",
            description="Find the gap in a strict-looking CSP header that still allows script execution.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Find the script-src Gap",
                prompt=(
                    "Inspect the CSP header from `$TARGET_URL/`, then confirm the bypass via "
                    "`$TARGET_URL/verify-bypass?src=data:...`."
                ),
                flag="flag{csp_bypass_data_uri}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "brute-force"):
        template = LabTemplate(
            name="Brute Force Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|brute-force-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="brute-force",
            title="Brute Force",
            difficulty="easy",
            description="Guess the admin password against a login endpoint with no lockout or rate limiting.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Guess the Admin Password",
                prompt=(
                    "Script a loop trying common passwords against "
                    "`POST $TARGET_URL/login` with `username=admin` until one succeeds."
                ),
                flag="flag{brute_force_no_lockout}",
                points=15,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "auth-bypass"):
        template = LabTemplate(
            name="Authentication Bypass Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|auth-bypass-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="auth-bypass",
            title="Authentication Bypass",
            difficulty="easy",
            description="Forge an unsigned identity cookie to gain admin access without ever logging in.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Forge the Trust Cookie",
                prompt=(
                    "Query `$TARGET_URL/account` with a hand-crafted "
                    "`Cookie: remember_me=admin` header - no login required."
                ),
                flag="flag{auth_bypass_trusted_cookie}",
                points=15,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "captcha-bypass"):
        template = LabTemplate(
            name="CAPTCHA Bypass Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|captcha-bypass-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="captcha-bypass",
            title="CAPTCHA Bypass",
            difficulty="easy",
            description="Find the logic hole that lets a sensitive action skip CAPTCHA verification entirely.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Skip the CAPTCHA Check",
                prompt=(
                    "POST to `$TARGET_URL/change-password` with `new_password` but with the "
                    "`captcha_answer` field omitted entirely (not just wrong)."
                ),
                flag="flag{captcha_bypass_no_verification}",
                points=10,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "javascript-obfuscation"):
        template = LabTemplate(
            name="JavaScript Obfuscation Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|javascript-obfuscation-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="javascript-obfuscation",
            title="JavaScript Obfuscation",
            difficulty="medium",
            description="Read an obfuscated client-side algorithm and reimplement it to forge a valid token.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Deobfuscate and Forge a Token",
                prompt=(
                    "Read `$TARGET_URL/verify.js`, get a seed from `$TARGET_URL/challenge`, "
                    "reimplement the transform yourself, and POST the matching token to `$TARGET_URL/verify`."
                ),
                flag="flag{js_obfuscation_deobfuscated}",
                points=25,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "cryptography"):
        template = LabTemplate(
            name="Cryptography Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|cryptography-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="cryptography",
            title="Cryptography",
            difficulty="medium",
            description="Crack an unsalted MD5-hashed 4-digit PIN by brute-forcing its tiny keyspace.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Crack the Weak Hash",
                prompt=(
                    "Fetch the MD5 hash from `$TARGET_URL/secret-hash`, brute-force all 10,000 "
                    "4-digit PINs, and confirm via `$TARGET_URL/verify-pin?pin=`."
                ),
                flag="flag{cryptography_weak_hash_cracked}",
                points=20,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "api-abuse"):
        template = LabTemplate(
            name="API Abuse Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|api-abuse-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="api-abuse",
            title="API Abuse (Mass Assignment)",
            difficulty="medium",
            description="Escalate to admin by PATCHing an API field that was never meant to be client-settable.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Escalate via Mass Assignment",
                prompt=(
                    "Log in via `$TARGET_URL/login`, then `PATCH $TARGET_URL/api/users/{id}` "
                    "with `{\"role\": \"admin\"}`, then request `$TARGET_URL/api/flag`."
                ),
                flag="flag{api_mass_assignment_privilege_escalation}",
                points=25,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if not await _room_exists(db, "info-disclosure"):
        template = LabTemplate(
            name="Info Disclosure Target",
            access_mode=LabAccessMode.WEB_TARGET.value,
            image="workspace-dev:latest|info-disclosure-target:latest",
            default_port=7681,
            target_port=8000,
            attacker_cpu=0.25,
            attacker_memory=256,
            target_cpu=0.25,
            target_memory=256,
        )
        room = Room(
            slug="info-disclosure",
            title="Information Disclosure",
            difficulty="easy",
            description="Read the page source for a hint pointing at a forgotten, still-accessible backup file.",
            is_published=True,
            template=template,
        )
        room.challenges.append(
            Challenge(
                title="Find the Leaked Backup",
                prompt=(
                    "View the HTML source of `$TARGET_URL/` for a hint, then request the file it mentions."
                ),
                flag="flag{info_disclosure_backup_leaked}",
                points=10,
                sort_order=1,
            )
        )
        db.add(room)
        changed = True

    if changed:
        await db.commit()

