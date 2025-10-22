package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	LicenseFile        string
	LicenseKey         string
	JWTToken           string
	PhoneHomeURL       string
	TargetAppPort      string
	CheckinInterval    time.Duration
	OfflineGracePeriod time.Duration
	MaxConcurrentUsers int
}

func Load() *Config {
	cfg := &Config{
		LicenseFile:        getEnv("LICENSE_FILE", "license.json"),
		LicenseKey:         getEnv("LICENSE_KEY", ""),
		JWTToken:           getEnv("JWT_TOKEN", ""),
		PhoneHomeURL:       getEnv("PHONE_HOME_URL", "http://localhost:8020"),
		TargetAppPort:      getEnv("TARGET_APP_PORT", "8080"),
		CheckinInterval:    getDurationEnv("CHECKIN_INTERVAL", "24h"),
		OfflineGracePeriod: getDurationEnv("OFFLINE_GRACE_PERIOD", "168h"), // 7 days
		MaxConcurrentUsers: getIntEnv("MAX_CONCURRENT_USERS", 0),
	}

	return cfg
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getIntEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getDurationEnv(key string, defaultValue string) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	
	duration, _ := time.ParseDuration(defaultValue)
	return duration
}