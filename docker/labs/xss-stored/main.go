// Intentionally vulnerable Stored XSS target (Go rewrite).
//
// /comment stores a guestbook entry as-is; /comments renders every entry back
// unescaped, so a persisted <script> tag reaches (and would execute for)
// every future visitor - mirroring DVWA's low-security-level stored XSS
// guestbook.
//
// /admin-check simulates the admin loading the guestbook page and flags
// whether a stored payload survived into the raw HTML unescaped.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
)

type comment struct {
	Author  string `json:"author"`
	Message string `json:"message"`
}

var (
	mu       sync.Mutex
	comments []comment
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Stored XSS Target</title></head>
  <body>
    <h1>Guestbook</h1>
    <p>Post: <code>POST /comment {"author": "...", "message": "..."}</code></p>
    <p>View: <code>GET /comments</code></p>
  </body>
</html>`)
}

func renderComments() string {
	mu.Lock()
	defer mu.Unlock()

	var rows strings.Builder
	for _, c := range comments {
		// Vulnerable: comment fields are interpolated directly into HTML with no escaping.
		fmt.Fprintf(&rows, "<li><strong>%s</strong>: %s</li>", c.Author, c.Message)
	}
	return fmt.Sprintf("<!doctype html><html><body><h1>Guestbook</h1><ul>%s</ul></body></html>", rows.String())
}

func postCommentHandler(w http.ResponseWriter, r *http.Request) {
	var c comment
	if err := json.NewDecoder(r.Body).Decode(&c); err != nil {
		http.Error(w, `{"error": "invalid request body"}`, http.StatusBadRequest)
		return
	}

	mu.Lock()
	comments = append(comments, c)
	total := len(comments)
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"stored":         true,
		"total_comments": total,
	})
}

func getCommentsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, renderComments())
}

func adminCheckHandler(w http.ResponseWriter, r *http.Request) {
	rendered := renderComments()
	w.Header().Set("Content-Type", "application/json")

	if strings.Contains(strings.ToLower(rendered), "<script") {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"triggered": true,
			"message":   "A stored script executed when the admin viewed the guestbook.",
			"flag":      "flag{stored_xss_admin_pwned}",
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"triggered": false,
		"message":   "No stored script found.",
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/", homeHandler)
	mux.HandleFunc("/comment", postCommentHandler)
	mux.HandleFunc("/comments", getCommentsHandler)
	mux.HandleFunc("/admin-check", adminCheckHandler)

	log.Println("xss-stored-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
