// Intentionally vulnerable Reflected XSS target (Go rewrite).
//
// /greet reflects the `name` parameter straight into the HTML response with no
// escaping, mirroring DVWA's low-security-level reflected XSS.
//
// Since the lab has no real browser to execute injected JavaScript,
// /report-to-admin simulates a victim ("admin bot") loading a crafted /greet
// URL and checks whether the payload survived into the raw HTML unescaped -
// the same bypass an attacker would need for the script to actually execute
// in a real browser.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Reflected XSS Target</title></head>
  <body>
    <h1>Greeting Service</h1>
    <p><code>GET /greet?name=YourName</code></p>
    <p>Get the admin to load your payload: <code>POST /report-to-admin {"payload": "..."}</code></p>
  </body>
</html>`)
}

func greetHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	if name == "" {
		name = "stranger"
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	// Vulnerable: user input rendered directly into HTML with no escaping.
	fmt.Fprintf(w, "<!doctype html><html><body><h1>Hello, %s!</h1></body></html>", name)
}

type reportRequest struct {
	Payload string `json:"payload"`
}

func reportToAdminHandler(w http.ResponseWriter, r *http.Request) {
	var req reportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error": "invalid request body"}`, http.StatusBadRequest)
		return
	}

	client := &http.Client{Timeout: 5 * time.Second}
	target := "http://127.0.0.1:8000/greet?name=" + url.QueryEscape(req.Payload)
	resp, err := client.Get(target)
	if err != nil {
		http.Error(w, `{"error": "failed to load admin page"}`, http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		http.Error(w, `{"error": "failed to read admin page"}`, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if strings.Contains(strings.ToLower(string(body)), "<script") {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"admin_visited": true,
			"message":       "The admin's browser executed your script.",
			"flag":          "flag{reflected_xss_confirmed}",
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"admin_visited": true,
		"message":       "No script tag reached the admin's page unescaped.",
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/", homeHandler)
	mux.HandleFunc("/greet", greetHandler)
	mux.HandleFunc("/report-to-admin", reportToAdminHandler)

	log.Println("xss-reflected-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
