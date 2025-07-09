const Redis = require('ioredis');
const config = require('../config/redis');

class RedisService {
  constructor() {
    this.client = null;
    this.isConnected = false;
    this.isConnecting = false;
    this.connectionAttempts = 0;
    this.maxConnectionAttempts = 5;
    this.fallbackMode = false;
    
    // Initialize connection if Redis is enabled
    if (config.features.enableRedis) {
      this.initialize();
    } else {
      console.log('Redis is disabled, running in fallback mode');
      this.fallbackMode = true;
    }
  }

  async initialize() {
    if (this.isConnecting) {
      console.log('Redis connection already in progress...');
      return;
    }

    this.isConnecting = true;
    this.connectionAttempts++;

    try {
      console.log(`Attempting to connect to Redis (attempt ${this.connectionAttempts}/${this.maxConnectionAttempts})...`);
      
      this.client = new Redis({
        ...config.redis,
        retryDelayOnFailover: config.redis.retryDelayOnFailover,
        retryDelayOnClusterDown: config.redis.retryDelayOnClusterDown,
        maxRetriesPerRequest: config.redis.maxRetriesPerRequest,
        lazyConnect: config.redis.lazyConnect
      });

      // Set up event listeners
      this.client.on('connect', () => {
        console.log('Redis client connected');
        this.isConnected = true;
        this.isConnecting = false;
        this.connectionAttempts = 0;
        this.fallbackMode = false;
      });

      this.client.on('ready', () => {
        console.log('Redis client ready for commands');
      });

      this.client.on('error', (error) => {
        console.error('Redis connection error:', error.message);
        this.handleConnectionError(error);
      });

      this.client.on('close', () => {
        console.log('Redis connection closed');
        this.isConnected = false;
      });

      this.client.on('reconnecting', () => {
        console.log('Redis client reconnecting...');
      });

      // Attempt connection
      await this.client.connect();
      
    } catch (error) {
      console.error('Failed to initialize Redis:', error.message);
      this.handleConnectionError(error);
    }
  }

  handleConnectionError(error) {
    this.isConnecting = false;
    this.isConnected = false;

    if (this.connectionAttempts >= this.maxConnectionAttempts) {
      console.warn(`Redis connection failed after ${this.maxConnectionAttempts} attempts. Enabling fallback mode.`);
      this.fallbackMode = true;
      this.connectionAttempts = 0;
    } else {
      // Retry connection after delay
      const retryDelay = Math.min(1000 * Math.pow(2, this.connectionAttempts), 30000);
      console.log(`Retrying Redis connection in ${retryDelay}ms...`);
      setTimeout(() => this.initialize(), retryDelay);
    }
  }

  // Core Redis operations with fallback
  async set(key, value, ttl = null) {
    if (this.fallbackMode || !this.isConnected) {
      console.debug(`Redis unavailable, skipping SET ${key}`);
      return false;
    }

    try {
      const serializedValue = JSON.stringify(value);
      
      if (ttl) {
        await this.client.setex(key, ttl, serializedValue);
      } else {
        await this.client.set(key, serializedValue);
      }
      
      return true;
    } catch (error) {
      console.error('Redis SET error:', error.message);
      return false;
    }
  }

  async get(key) {
    if (this.fallbackMode || !this.isConnected) {
      console.debug(`Redis unavailable, skipping GET ${key}`);
      return null;
    }

    try {
      const value = await this.client.get(key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      console.error('Redis GET error:', error.message);
      return null;
    }
  }

  async del(key) {
    if (this.fallbackMode || !this.isConnected) {
      console.debug(`Redis unavailable, skipping DEL ${key}`);
      return false;
    }

    try {
      const result = await this.client.del(key);
      return result > 0;
    } catch (error) {
      console.error('Redis DEL error:', error.message);
      return false;
    }
  }

  async exists(key) {
    if (this.fallbackMode || !this.isConnected) {
      return false;
    }

    try {
      const result = await this.client.exists(key);
      return result === 1;
    } catch (error) {
      console.error('Redis EXISTS error:', error.message);
      return false;
    }
  }

  async expire(key, ttl) {
    if (this.fallbackMode || !this.isConnected) {
      return false;
    }

    try {
      const result = await this.client.expire(key, ttl);
      return result === 1;
    } catch (error) {
      console.error('Redis EXPIRE error:', error.message);
      return false;
    }
  }

  async keys(pattern) {
    if (this.fallbackMode || !this.isConnected) {
      return [];
    }

    try {
      return await this.client.keys(pattern);
    } catch (error) {
      console.error('Redis KEYS error:', error.message);
      return [];
    }
  }

  // Utility methods
  isAvailable() {
    return !this.fallbackMode && this.isConnected;
  }

  getStatus() {
    return {
      connected: this.isConnected,
      fallbackMode: this.fallbackMode,
      connectionAttempts: this.connectionAttempts,
      redisEnabled: config.features.enableRedis
    };
  }

  async ping() {
    if (this.fallbackMode || !this.isConnected) {
      return false;
    }

    try {
      const result = await this.client.ping();
      return result === 'PONG';
    } catch (error) {
      console.error('Redis PING error:', error.message);
      return false;
    }
  }

  // Graceful shutdown
  async disconnect() {
    if (this.client && this.isConnected) {
      try {
        await this.client.quit();
        console.log('Redis connection closed gracefully');
      } catch (error) {
        console.error('Error closing Redis connection:', error.message);
      }
    }
  }
}

// Create singleton instance
const redisService = new RedisService();

module.exports = redisService; 