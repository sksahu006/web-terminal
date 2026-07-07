// Intentionally vulnerable Weak Session IDs target.
//
// Session cookies are issued as a plain, sequentially incrementing counter
// (mirroring DVWA's low-security-level `dvwaSession = lastId + 1` flaw). At
// startup, an admin session is pre-created as id "1" - representing an admin
// who is already logged in elsewhere. A student who studies the pattern can
// simply guess a small session id (starting from "1") to hijack the admin's
// session without ever knowing their password.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"sync"
)

var (
	mu           sync.Mutex
	nextID       int
	sessionOwner = map[string]string{}
)

const adminPassword = "correct-horse-battery-staple"

func createSession(username string) string {
	mu.Lock()
	defer mu.Unlock()
	nextID++
	id := strconv.Itoa(nextID)
	sessionOwner[id] = username
	return id
}

func lookupSession(id string) (string, bool) {
	mu.Lock()
	defer mu.Unlock()
	username, ok := sessionOwner[id]
	return username, ok
}

func init() {
	// The admin "already logged in" before any student reaches the lab,
	// deterministically claiming session id "1".
	createSession("admin")
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Weak Session IDs Target",
		"login":   `POST /login {"username": "guest", "password": "guest123"}`,
		"whoami":  "GET /whoami (uses Cookie: session=<id>)",
		"flag":    "GET /flag (requires an admin session cookie)",
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

	if req.Username != "guest" || req.Password != "guest123" {
		http.Error(w, `{"authenticated": false}`, http.StatusUnauthorized)
		return
	}

	// Vulnerable: session id is a predictable sequential counter, not a
	// cryptographically random value.
	id := createSession(req.Username)
	http.SetCookie(w, &http.Cookie{Name: "session", Value: id, Path: "/"})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"authenticated": true,
		"session_id":    id,
	})
}

func whoamiHandler(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie("session")
	w.Header().Set("Content-Type", "application/json")
	if err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"authenticated": false})
		return
	}

	username, ok := lookupSession(cookie.Value)
	if !ok {
		json.NewEncoder(w).Encode(map[string]interface{}{"authenticated": false})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{"authenticated": true, "username": username})
}

func flagHandler(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie("session")
	w.Header().Set("Content-Type", "application/json")
	if err != nil {
		http.Error(w, `{"error": "not authenticated"}`, http.StatusUnauthorized)
		return
	}

	username, ok := lookupSession(cookie.Value)
	if !ok || username != "admin" {
		http.Error(w, `{"error": "admin session required"}`, http.StatusForbidden)
		return
	}

	json.NewEncoder(w).Encode(map[string]string{"flag": "flag{weak_session_hijacked}"})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("POST /login", loginHandler)
	mux.HandleFunc("GET /whoami", whoamiHandler)
	mux.HandleFunc("GET /flag", flagHandler)

	fmt.Println("weak-session-ids-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
