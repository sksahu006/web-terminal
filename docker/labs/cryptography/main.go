// Intentionally vulnerable Cryptography target.
//
// A 4-digit PIN is "protected" only by an unsalted MD5 hash - the classic
// weak-cryptography lesson: a 10,000-value keyspace hashed with a fast,
// unsalted algorithm is crackable by brute force in seconds, regardless of
// how "encrypted" it looks.
package main

import (
	"crypto/md5"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math/big"
	"net/http"
)

var pinHash string

func generatePin() string {
	n, _ := rand.Int(rand.Reader, big.NewInt(10000))
	return fmt.Sprintf("%04d", n.Int64())
}

func md5Hex(s string) string {
	sum := md5.Sum([]byte(s))
	return hex.EncodeToString(sum[:])
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message":     "Cryptography Target",
		"secret_hash": "GET /secret-hash",
		"verify":      "GET /verify-pin?pin=0000",
	})
}

func secretHashHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"algorithm": "md5",
		"hash":      pinHash,
		"hint":      "It's a 4-digit PIN (0000-9999). MD5 has no salt and no rate limit here.",
	})
}

func verifyPinHandler(w http.ResponseWriter, r *http.Request) {
	pin := r.URL.Query().Get("pin")
	w.Header().Set("Content-Type", "application/json")

	// Vulnerable: unsalted, fast hash over a tiny (10,000-value) keyspace -
	// trivially brute-forceable, and this endpoint applies no rate limiting.
	if md5Hex(pin) == pinHash {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"correct": true,
			"flag":    "flag{cryptography_weak_hash_cracked}",
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{"correct": false})
}

func main() {
	pinHash = md5Hex(generatePin())

	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /secret-hash", secretHashHandler)
	mux.HandleFunc("GET /verify-pin", verifyPinHandler)

	fmt.Println("cryptography-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
