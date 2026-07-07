// Intentionally "vulnerable" JavaScript Obfuscation target.
//
// The real logic that unlocks /verify lives in client-side JS (verify.js),
// obfuscated with meaningless variable names to discourage casual reading -
// mirroring DVWA's JavaScript module, where security depends on a client
// never reading (or reimplementing) the obfuscated algorithm themselves.
//
// The lab has no real browser to execute verify.js, so the point is exactly
// what a real attacker would do anyway: read through the obfuscated source,
// reverse-engineer the transform, reimplement it independently (in the
// attacker terminal), and submit a correct token without ever running the
// original script.
package main

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"os"
)

const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

func randomSeed(n int) string {
	b := make([]byte, n)
	for i := range b {
		idx, _ := rand.Int(rand.Reader, big.NewInt(int64(len(charset))))
		b[i] = charset[idx.Int64()]
	}
	return string(b)
}

// computeToken mirrors verify.js's computeToken() exactly: reverse the seed,
// shift each character code by +3, then base64-encode the result.
func computeToken(seed string) string {
	runes := []rune(seed)
	for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
		runes[i], runes[j] = runes[j], runes[i]
	}
	shifted := make([]byte, len(runes))
	for i, r := range runes {
		shifted[i] = byte(r) + 3
	}
	return base64.StdEncoding.EncodeToString(shifted)
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message":   "JavaScript Obfuscation Target",
		"source":    "GET /verify.js",
		"challenge": "GET /challenge",
		"verify":    `POST /verify {"seed": "...", "token": "..."}`,
	})
}

func verifyJsHandler(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "/app/verify.js")
}

func challengeHandler(w http.ResponseWriter, r *http.Request) {
	seed := randomSeed(8)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"seed": seed})
}

type verifyRequest struct {
	Seed  string `json:"seed"`
	Token string `json:"token"`
}

func verifyHandler(w http.ResponseWriter, r *http.Request) {
	var req verifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error": "invalid request body"}`, http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")

	expected := computeToken(req.Seed)
	if req.Token == expected {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"verified": true,
			"flag":     "flag{js_obfuscation_deobfuscated}",
		})
		return
	}

	w.WriteHeader(http.StatusForbidden)
	json.NewEncoder(w).Encode(map[string]interface{}{"verified": false})
}

func main() {
	if _, err := os.Stat("/app/verify.js"); err != nil {
		log.Fatal("verify.js missing from image")
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /verify.js", verifyJsHandler)
	mux.HandleFunc("GET /challenge", challengeHandler)
	mux.HandleFunc("POST /verify", verifyHandler)

	fmt.Println("javascript-obfuscation-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
