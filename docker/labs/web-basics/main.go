// Small intentionally vulnerable target for the Web Basics room.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Web Basics Target</title></head>
  <body>
    <h1>Web Basics Target</h1>
    <p>The attacker terminal can reach this private target through TARGET_URL.</p>
    <p>Homepage flag: <code>flag{web_target_reachable}</code></p>
    <p>Hint: debug endpoints often reveal more than they should.</p>
  </body>
</html>`)
}

func debugHandler(w http.ResponseWriter, r *http.Request) {
	show := r.URL.Query().Get("show")
	w.Header().Set("Content-Type", "application/json")

	if show == "flag" {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"debug": true,
			"flag":  "flag{debug_endpoint_found}",
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"debug": true,
		"hint":  "Try show=flag",
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /debug", debugHandler)

	fmt.Println("web-basics-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
