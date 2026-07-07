// Intentionally vulnerable Open Redirect target.
//
// /redirect issues a 302 to whatever `url` the caller supplies, with no
// same-origin/whitelist validation - mirroring DVWA/OWASP's classic open
// redirect flaw, which attackers abuse to make a trusted-looking link
// silently forward victims to a phishing site.
//
// Since the lab sandbox can't reach the public internet to actually
// demonstrate a real phishing hop, the response carries an X-Redirect-Flag
// header whenever the target `url` points off-site - proof the redirect
// would have sent a real browser somewhere the site never validated.
package main

import (
	"fmt"
	"log"
	"net/http"
	"strings"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Open Redirect Target</title></head>
  <body>
    <h1>Link Shortener</h1>
    <p><code>GET /redirect?url=https://example.com</code></p>
  </body>
</html>`)
}

func redirectHandler(w http.ResponseWriter, r *http.Request) {
	target := r.URL.Query().Get("url")
	if target == "" {
		http.Error(w, "missing url parameter", http.StatusBadRequest)
		return
	}

	// Vulnerable: no check that `target` stays on this site (e.g. a leading
	// "/" relative path) before redirecting to it.
	isOffSite := strings.HasPrefix(target, "http://") || strings.HasPrefix(target, "https://") || strings.HasPrefix(target, "//")
	if isOffSite {
		w.Header().Set("X-Redirect-Flag", "flag{open_redirect_exploited}")
	}

	http.Redirect(w, r, target, http.StatusFound)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /redirect", redirectHandler)

	fmt.Println("open-redirect-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
