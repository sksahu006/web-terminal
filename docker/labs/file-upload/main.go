// Intentionally vulnerable Unrestricted File Upload target (Go rewrite).
//
// /upload saves any file exactly as submitted with no extension/MIME/content
// checks, mirroring DVWA's low-security-level move_uploaded_file() flaw.
//
// /run/{filename} then executes an uploaded file as a shell script, giving
// the same "upload a webshell, then browse to it" RCE chain DVWA teaches with
// PHP: a student who uploads a shell payload can read the target's flag file.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
)

const (
	uploadDir      = "/app/uploads"
	maxUploadBytes = 512 * 1024 // generous cap so a stray large upload can't fill the container disk
)

var unsafeChars = regexp.MustCompile(`[/\\]`)

func sanitizeFilename(name string) string {
	if name == "" {
		name = "upload.bin"
	}
	return unsafeChars.ReplaceAllString(name, "_")
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "File Upload Target",
		"upload":  "POST /upload (multipart file field 'file')",
		"list":    "GET /uploads",
		"run":     "GET /run/{filename}",
	})
}

func uploadHandler(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxUploadBytes+1024)
	if err := r.ParseMultipartForm(maxUploadBytes + 1024); err != nil {
		http.Error(w, `{"error": "file too large or malformed"}`, http.StatusRequestEntityTooLarge)
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		http.Error(w, `{"error": "missing file field"}`, http.StatusBadRequest)
		return
	}
	defer file.Close()

	// Vulnerable: no extension whitelist, no MIME check, filename used as-is
	// (only stripped of path separators so the upload can't escape the folder).
	safeName := sanitizeFilename(header.Filename)
	destination := filepath.Join(uploadDir, safeName)

	out, err := os.Create(destination)
	if err != nil {
		http.Error(w, `{"error": "failed to save file"}`, http.StatusInternalServerError)
		return
	}
	defer out.Close()

	written, err := io.Copy(out, io.LimitReader(file, maxUploadBytes+1))
	if err != nil {
		http.Error(w, `{"error": "failed to save file"}`, http.StatusInternalServerError)
		return
	}
	if written > maxUploadBytes {
		os.Remove(destination)
		http.Error(w, `{"error": "file too large"}`, http.StatusRequestEntityTooLarge)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"uploaded": safeName,
		"size":     written,
	})
}

func listUploadsHandler(w http.ResponseWriter, r *http.Request) {
	entries, err := os.ReadDir(uploadDir)
	if err != nil {
		http.Error(w, `{"error": "failed to list uploads"}`, http.StatusInternalServerError)
		return
	}

	names := make([]string, 0, len(entries))
	for _, e := range entries {
		names = append(names, e.Name())
	}
	sort.Strings(names)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"files": names})
}

func runUploadedHandler(w http.ResponseWriter, r *http.Request) {
	safeName := sanitizeFilename(r.PathValue("filename"))
	path := filepath.Join(uploadDir, safeName)

	if _, err := os.Stat(path); err != nil {
		http.Error(w, `{"error": "file not found"}`, http.StatusNotFound)
		return
	}

	// Vulnerable: any uploaded file is executed as a shell script with no
	// validation of its origin or content.
	var stdout, stderr bytes.Buffer
	cmd := exec.Command("sh", path)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	cmd.Run()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"stdout": stdout.String(),
		"stderr": stderr.String(),
	})
}

func main() {
	if err := os.MkdirAll(uploadDir, 0o755); err != nil {
		log.Fatal(err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", homeHandler)
	mux.HandleFunc("POST /upload", uploadHandler)
	mux.HandleFunc("GET /uploads", listUploadsHandler)
	mux.HandleFunc("GET /run/{filename}", runUploadedHandler)

	fmt.Println("file-upload-target listening on :8000")
	if err := http.ListenAndServe(":8000", mux); err != nil {
		log.Fatal(err)
	}
}
