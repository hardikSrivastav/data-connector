package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"ceneca-license-agent/internal/agent"
	"ceneca-license-agent/internal/config"

	"github.com/gorilla/mux"
	"github.com/joho/godotenv"
)

func main() {
	// Load environment variables
	godotenv.Load()

	// Load configuration
	cfg := config.Load()

	// Create license agent
	licenseAgent, err := agent.New(cfg)
	if err != nil {
		log.Fatalf("Failed to create license agent: %v", err)
	}

	// Start the agent
	if err := licenseAgent.Start(); err != nil {
		log.Fatalf("Failed to start license agent: %v", err)
	}

	// Set up HTTP server for health checks and status
	router := mux.NewRouter()
	
	// Health check endpoint
	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"ceneca-license-agent"}`))
	}).Methods("GET")

	// Status endpoint
	router.HandleFunc("/status", licenseAgent.StatusHandler).Methods("GET")

	// License validation endpoint (for local app integration)
	router.HandleFunc("/validate", licenseAgent.ValidateHandler).Methods("POST")

	// User session management
	router.HandleFunc("/session/login", licenseAgent.LoginHandler).Methods("POST")
	router.HandleFunc("/session/logout", licenseAgent.LogoutHandler).Methods("POST")
	router.HandleFunc("/session/active", licenseAgent.ActiveSessionsHandler).Methods("GET")

	port := os.Getenv("PORT")
	if port == "" {
		port = "9020"
	}

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	log.Printf("Ceneca License Agent starting on port %s", port)
	log.Printf("License Key: %s", cfg.LicenseKey)
	log.Printf("Phone Home URL: %s", cfg.PhoneHomeURL)
	
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}