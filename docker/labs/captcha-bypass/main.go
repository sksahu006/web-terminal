// Intentionally vulnerable CAPTCHA Bypass target.
//
// /change-password is meant to require solving the math challenge from
// /captcha before processing a sensitive action - but the verification logic
// only runs when a `captcha_answer` field is present at all. Omit the field
// entirely and the flawed check silently treats "no answer given" as
// "not applicable", mirroring DVWA's low-security-level CAPTCHA module where
// the server never actually enforces the challenge.
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
		"message": "CAPTCHA Bypass Target",
		"captcha": "GET /captcha",
		"change":  `POST /change-password {"new_password": "...", "captcha_answer": "..."}`,
	})
}

func captchaHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"question": "3 + 4",
		"hint":     "Solve this and send it back as captcha_answer - or don't.",
	})
}

type changePasswordRequest struct {
	NewPassword   string  `json:"new_password"`
	CaptchaAnswer *string `json:"captcha_answer"`
}

func changePasswordHandler(w http.ResponseWriter, r *http.Request) {
	var req changePasswordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error": "invalid request body"}`, http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")

	// Vulnerable: verification is only performed when the field is present
	// at all. Omitting `captcha_answer` bypasses the check entirely instead
	// of failing closed.
	if req.CaptchaAnswer != nil && *req.CaptchaAnswer != "7" {
		w.WriteHeader(http.StatusForbidden)
		json.NewEncoder(w).Encode(map[string]interface{}{"error": "incorrect captcha"})
		return
	}

	response := map[string]interface{}{
		"changed":      true,
		"new_password": req.NewPassword,
	}
	if req.CaptchaAnswer == nil {
		response["flag"] = "flag{captcha_bypass_no_verification}"
	}

	json.NewEncoder(w).Encode(response)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("GET /captcha", captchaHandler)
	mux.HandleFunc("POST /change-password", changePasswordHandler)

	fmt.Println("captcha-bypass-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
