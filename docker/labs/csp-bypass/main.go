// Intentionally vulnerable Content-Security-Policy target.
//
// The page ships a CSP header that looks strict at a glance
// (`default-src 'self'`) but includes `data:` in `script-src` - a real,
// commonly-seen misconfiguration. `data:` URIs let a <script src="data:...">
// tag execute attacker-controlled JavaScript despite the policy nominally
// restricting scripts to same-origin.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
)

const cspHeader = "default-src 'self'; script-src 'self' data:; object-src 'none'"

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Security-Policy", cspHeader)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprintf(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>CSP Bypass Target</title></head>
  <body>
    <h1>Notes App</h1>
    <p>Content-Security-Policy: <code>%s</code></p>
    <p>Find the gap in this policy, then confirm it: <code>GET /verify-bypass?src=&lt;script-src-value&gt;</code></p>
  </body>
</html>`, cspHeader)
}

func verifyBypassHandler(w http.ResponseWriter, r *http.Request) {
	src := r.URL.Query().Get("src")

	w.Header().Set("Content-Type", "application/json")

	// Vulnerable: script-src allows the `data:` scheme, so any
	// `<script src="data:text/javascript,...">` payload runs despite the
	// policy otherwise restricting scripts to 'self'.
	if strings.HasPrefix(src, "data:") {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"bypassed": true,
			"message":  "The CSP's script-src allows data: URIs - your script would have executed.",
			"flag":     "flag{csp_bypass_data_uri}",
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"bypassed": false,
		"message":  "That script source is still blocked by this policy.",
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /verify-bypass", verifyBypassHandler)

	fmt.Println("csp-bypass-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
