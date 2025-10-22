package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"sync"
	"time"

	"ceneca-license-agent/internal/config"
	"ceneca-license-agent/internal/license"
	"ceneca-license-agent/internal/telemetry"
	"ceneca-license-agent/internal/session"
)

type Agent struct {
	config          *config.Config
	license         *license.License
	sessionManager  *session.Manager
	telemetryBuffer *telemetry.Buffer
	
	// State
	isOnline        bool
	lastPhoneHome   time.Time
	startTime       time.Time
	
	// Synchronization
	mu     sync.RWMutex
	ctx    context.Context
	cancel context.CancelFunc
}

func New(cfg *config.Config) (*Agent, error) {
	// Load license
	lic, err := license.LoadFromFile(cfg.LicenseFile)
	if err != nil {
		// Try loading from environment variables
		if cfg.LicenseKey != "" && cfg.JWTToken != "" {
			lic = &license.License{
				LicenseKey: cfg.LicenseKey,
				JWTToken:   cfg.JWTToken,
			}
			
			// Validate JWT token
			if err := lic.Validate(); err != nil {
				return nil, fmt.Errorf("license validation failed: %w", err)
			}
		} else {
			return nil, fmt.Errorf("no valid license found: %w", err)
		}
	}

	// Override max users from config if set
	if cfg.MaxConcurrentUsers > 0 {
		lic.MaxSeats = cfg.MaxConcurrentUsers
	}

	ctx, cancel := context.WithCancel(context.Background())

	agent := &Agent{
		config:          cfg,
		license:         lic,
		sessionManager:  session.NewManager(lic.MaxSeats),
		telemetryBuffer: telemetry.NewBuffer(),
		startTime:       time.Now(),
		ctx:            ctx,
		cancel:         cancel,
	}

	return agent, nil
}

func (a *Agent) Start() error {
	a.mu.Lock()
	defer a.mu.Unlock()

	log.Printf("Starting Ceneca License Agent")
	log.Printf("License: %s (%s plan, %d max seats)", a.license.LicenseKey, a.license.Plan, a.license.MaxSeats)

	// Validate license on startup
	if err := a.license.Validate(); err != nil {
		// Check if we're within offline grace period
		if time.Since(a.lastPhoneHome) > a.config.OfflineGracePeriod {
			return fmt.Errorf("license validation failed and offline grace period exceeded: %w", err)
		}
		log.Printf("License validation failed, but within offline grace period: %v", err)
	}

	// Start background routines
	go a.phoneHomeRoutine()
	go a.telemetryCollectionRoutine()

	// Initial phone home
	go func() {
		time.Sleep(5 * time.Second) // Give services time to start
		a.phoneHome()
	}()

	return nil
}

func (a *Agent) Stop() {
	log.Printf("Stopping Ceneca License Agent")
	a.cancel()
	
	// Send final telemetry
	a.phoneHome()
}

func (a *Agent) phoneHomeRoutine() {
	ticker := time.NewTicker(a.config.CheckinInterval)
	defer ticker.Stop()

	for {
		select {
		case <-a.ctx.Done():
			return
		case <-ticker.C:
			a.phoneHome()
		}
	}
}

func (a *Agent) phoneHome() {
	a.mu.Lock()
	defer a.mu.Unlock()

	// Collect telemetry data
	telemetryData := a.collectTelemetryData()
	
	// Send to cloud service
	if err := a.sendTelemetry(telemetryData); err != nil {
		log.Printf("Phone home failed: %v", err)
		a.isOnline = false
	} else {
		log.Printf("Phone home successful")
		a.isOnline = true
		a.lastPhoneHome = time.Now()
		
		// Clear telemetry buffer after successful send
		a.telemetryBuffer.Clear()
	}
}

func (a *Agent) collectTelemetryData() *telemetry.Data {
	sessions := a.sessionManager.GetActiveSessions()
	
	// Get unique users and peak concurrent
	uniqueUsers := make(map[string]bool)
	var userList []string
	
	for _, session := range sessions {
		if !uniqueUsers[session.UserID] {
			uniqueUsers[session.UserID] = true
			userList = append(userList, session.UserID)
		}
	}

	// Get system info
	systemInfo := map[string]interface{}{
		"version":       "1.0.0",
		"os":           runtime.GOOS,
		"arch":         runtime.GOARCH,
		"go_version":   runtime.Version(),
		"deployment_id": getDeploymentID(),
	}

	// Aggregate usage stats from buffer
	usageStats := a.telemetryBuffer.GetAggregatedStats()

	return &telemetry.Data{
		LicenseKey: a.license.LicenseKey,
		ReportDate: time.Now(),
		DeploymentID: getDeploymentID(),
		ActiveUsers: map[string]interface{}{
			"unique_daily":     len(uniqueUsers),
			"peak_concurrent":  len(sessions),
			"user_list":       userList,
		},
		UsageStats: usageStats,
		SystemInfo: systemInfo,
	}
}

func (a *Agent) sendTelemetry(data *telemetry.Data) error {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal telemetry data: %w", err)
	}

	url := fmt.Sprintf("%s/api/telemetry/phone-home", a.config.PhoneHomeURL)
	
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to send telemetry: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("phone home failed with status: %d", resp.StatusCode)
	}

	// Parse response for any warnings or actions
	var response struct {
		Status      string `json:"status"`
		Warning     string `json:"warning,omitempty"`
		OverageSeats int   `json:"overage_seats,omitempty"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&response); err == nil {
		if response.Warning != "" {
			log.Printf("LICENSE WARNING: %s", response.Warning)
		}
		if response.OverageSeats > 0 {
			log.Printf("SEAT OVERAGE: %d seats over limit", response.OverageSeats)
		}
	}

	return nil
}

func (a *Agent) telemetryCollectionRoutine() {
	ticker := time.NewTicker(5 * time.Minute) // Collect stats every 5 minutes
	defer ticker.Stop()

	for {
		select {
		case <-a.ctx.Done():
			return
		case <-ticker.C:
			// Add current session count to telemetry buffer
			sessionCount := a.sessionManager.GetActiveSessionCount()
			a.telemetryBuffer.AddEvent("session_count", map[string]interface{}{
				"count":     sessionCount,
				"timestamp": time.Now(),
			})
		}
	}
}

func getDeploymentID() string {
	// Try to get from environment
	if id := os.Getenv("DEPLOYMENT_ID"); id != "" {
		return id
	}
	
	// Generate based on hostname
	hostname, err := os.Hostname()
	if err != nil {
		return "unknown"
	}
	
	return fmt.Sprintf("%s-%d", hostname, time.Now().Unix())
}