// Intentionally vulnerable Authentication Bypass target.
//
// /account trusts a `remember_me` cookie's value as the logged-in username
// with zero verification - no signature, no HMAC, no server-side session
// lookup. Unlike the Weak Session IDs lab (predictable but server-issued
// tokens), this flaw lets an attacker fabricate an entirely arbitrary
// identity cookie and be trusted outright.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Authentication Bypass Target",
		"account": "GET /account (uses Cookie: remember_me=<username>)",
	})
}

func accountHandler(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie("remember_me")
	w.Header().Set("Content-Type", "application/json")

	if err != nil || cookie.Value == "" {
		http.Error(w, `{"error": "not authenticated"}`, http.StatusUnauthorized)
		return
	}

	// Vulnerable: the cookie value is trusted as the identity outright - no
	// signature or server-side record ties it to a real login event.
	username := cookie.Value
	response := map[string]interface{}{
		"authenticated": true,
		"username":      username,
	}
	if username == "admin" {
		response["flag"] = "flag{auth_bypass_trusted_cookie}"
	}

	json.NewEncoder(w).Encode(response)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /account", accountHandler)

	fmt.Println("auth-bypass-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
