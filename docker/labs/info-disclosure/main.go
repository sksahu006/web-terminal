// Intentionally vulnerable Information Disclosure target.
//
// The homepage leaks an HTML comment pointing at a "forgotten" backup file
// that was never removed before deploy and is still served with no access
// control - mirroring DVWA's help/view-source lesson that sensitive info
// often leaks through things developers assume nobody reads (comments,
// stray build artifacts, verbose debug output).
package main

import (
	"fmt"
	"log"
	"net/http"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Info Disclosure Target</title></head>
  <body>
    <h1>Company Site</h1>
    <p>Nothing to see here.</p>
    <!-- TODO: remove /backup.zip before deploy, still has the prod credentials in it -->
  </body>
</html>`)
}

func backupHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprint(w, "admin_password=flag{info_disclosure_backup_leaked}\n")
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /backup.zip", backupHandler)

	fmt.Println("info-disclosure-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
