// Intentionally vulnerable Brute Force target.
//
// /login accepts unlimited login attempts with no rate limiting, no account
// lockout, and no artificial delay - mirroring DVWA's low-security-level
// brute force module. The admin password is a common, guessable value so a
// short wordlist attack (a bash/curl loop) succeeds quickly.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

const (
	validUsername = "admin"
	validPassword = "letmein123"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Brute Force Target",
		"login":   `POST /login {"username": "admin", "password": "..."}`,
	})
}

type loginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func loginHandler(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error": "invalid request body"}`, http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")

	// Vulnerable: no lockout counter, no delay, no CAPTCHA after repeated
	// failures - every attempt is answered instantly regardless of history.
	if req.Username == validUsername && req.Password == validPassword {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"authenticated": true,
			"flag":          "flag{brute_force_no_lockout}",
		})
		return
	}

	w.WriteHeader(http.StatusUnauthorized)
	json.NewEncoder(w).Encode(map[string]interface{}{"authenticated": false})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("POST /login", loginHandler)

	fmt.Println("brute-force-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
