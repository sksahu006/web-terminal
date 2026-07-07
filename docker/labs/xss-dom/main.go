// Intentionally vulnerable DOM-based XSS target.
//
// /welcome serves a page whose inline JS writes the URL fragment
// (`location.hash`) straight into the DOM via document.write with no
// escaping - mirroring DVWA's low-security-level DOM XSS module. The
// fragment is never sent to the server (that's what makes it a DOM sink,
// not a reflected one), so a real browser is what actually executes it.
//
// Since this lab sandbox has no real browser, /admin-check-dom simulates
// what document.write would produce for a given hash value and reports
// whether it would have executed a script tag.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "DOM XSS Target",
		"welcome": "GET /welcome#YourName (open in a real browser - the hash never reaches this server)",
		"check":   "GET /admin-check-dom?hash=<payload> (simulates what the DOM sink would render)",
	})
}

func welcomeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	// Vulnerable: the inline script writes location.hash directly into the
	// page with no escaping. This never touches the server - a real browser
	// evaluates it entirely client-side.
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>DOM XSS Target</title></head>
  <body>
    <div id="greeting"></div>
    <script>
      var name = decodeURIComponent(location.hash.substring(1)) || "stranger";
      document.getElementById("greeting").innerHTML = "Welcome, " + name + "!";
    </script>
  </body>
</html>`)
}

func adminCheckDomHandler(w http.ResponseWriter, r *http.Request) {
	hash := r.URL.Query().Get("hash")
	decoded, err := url.QueryUnescape(hash)
	if err != nil {
		decoded = hash
	}

	rendered := "Welcome, " + decoded + "!"

	w.Header().Set("Content-Type", "application/json")
	if strings.Contains(strings.ToLower(rendered), "<script") || strings.Contains(strings.ToLower(rendered), "<img") {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"triggered": true,
			"message":   "The DOM sink rendered your payload unescaped - a real browser would have executed it.",
			"flag":      "flag{dom_xss_confirmed}",
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"triggered": false,
		"message":   "No executable markup reached the DOM sink.",
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /welcome", welcomeHandler)
	mux.HandleFunc("GET /admin-check-dom", adminCheckDomHandler)

	fmt.Println("xss-dom-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
