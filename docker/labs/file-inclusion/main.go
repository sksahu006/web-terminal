// Intentionally vulnerable Local File Inclusion target.
//
// /page concatenates the `file` parameter directly onto the pages directory
// with no path sanitization, so `../` traversal escapes it and reads
// arbitrary files elsewhere on the container's filesystem - mirroring DVWA's
// low-security-level `include($file)` flaw.
package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
)

const pagesDir = "/app/pages"

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>File Inclusion Target</title></head>
  <body>
    <h1>Help Pages</h1>
    <p><code>GET /page?file=page1.txt</code></p>
    <p><code>GET /page?file=page2.txt</code></p>
  </body>
</html>`)
}

func pageHandler(w http.ResponseWriter, r *http.Request) {
	file := r.URL.Query().Get("file")
	if file == "" {
		file = "page1.txt"
	}

	// Vulnerable: no path sanitization or whitelist - `file=../secret.txt`
	// (or deeper traversal) escapes the pages directory entirely.
	path := filepath.Join(pagesDir, file)

	contents, err := os.ReadFile(path)
	if err != nil {
		http.Error(w, "page not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.Write(contents)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /page", pageHandler)

	fmt.Println("file-inclusion-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
