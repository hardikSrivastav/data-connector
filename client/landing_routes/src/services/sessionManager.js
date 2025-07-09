const { v4: uuidv4 } = require('uuid');
const redisService = require('./redisService');
const config = require('../config/redis');

class SessionManager {
  constructor() {
    this.activeSessions = new Map(); // Fallback storage when Redis unavailable
  }

  /**
   * Generate a new conversation ID
   */
  generateConversationId() {
    return uuidv4();
  }

  /**
   * Validate conversation ID format
   */
  isValidConversationId(conversationId) {
    if (!conversationId || typeof conversationId !== 'string') {
      return false;
    }
    
    // Check UUID v4 format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(conversationId);
  }

  /**
   * Create a new session
   */
  async createSession(userInfo = {}) {
    const conversationId = this.generateConversationId();
    const timestamp = new Date();
    
    const sessionData = {
      id: conversationId,
      userInfo,
      createdAt: timestamp,
      lastAccessed: timestamp,
      status: 'active'
    };

    // Store in Redis with TTL
    if (redisService.isAvailable()) {
      const sessionKey = config.keys.session(conversationId);
      await redisService.set(sessionKey, sessionData, config.redis.defaultTTL);
      
      // Add to active sessions index
      await this.addToActiveIndex(conversationId);
    } else {
      // Fallback to in-memory storage
      this.activeSessions.set(conversationId, sessionData);
    }

    console.log(`Created new session: ${conversationId}`);
    return {
      conversationId,
      sessionData
    };
  }

  /**
   * Validate and recover an existing session
   */
  async validateSession(conversationId) {
    if (!this.isValidConversationId(conversationId)) {
      return { valid: false, reason: 'invalid_format' };
    }

    let sessionData = null;

    // Try Redis first
    if (redisService.isAvailable()) {
      const sessionKey = config.keys.session(conversationId);
      sessionData = await redisService.get(sessionKey);
      
      if (sessionData) {
        // Extend TTL on access
        await redisService.expire(sessionKey, config.redis.extendTTL);
        await this.updateLastAccessed(conversationId);
      }
    } else {
      // Fallback to in-memory
      sessionData = this.activeSessions.get(conversationId);
    }

    if (!sessionData) {
      return { valid: false, reason: 'session_not_found' };
    }

    // Check if session is expired (additional safety check)
    const now = new Date();
    const lastAccessed = new Date(sessionData.lastAccessed);
    const maxAge = config.redis.defaultTTL * 1000; // Convert to milliseconds
    
    if (now - lastAccessed > maxAge) {
      await this.destroySession(conversationId);
      return { valid: false, reason: 'session_expired' };
    }

    return {
      valid: true,
      sessionData,
      conversationId
    };
  }

  /**
   * Update last accessed timestamp
   */
  async updateLastAccessed(conversationId) {
    const timestamp = new Date();

    if (redisService.isAvailable()) {
      const sessionKey = config.keys.session(conversationId);
      const sessionData = await redisService.get(sessionKey);
      
      if (sessionData) {
        sessionData.lastAccessed = timestamp;
        await redisService.set(sessionKey, sessionData, config.redis.extendTTL);
      }
    } else {
      // Fallback to in-memory
      const sessionData = this.activeSessions.get(conversationId);
      if (sessionData) {
        sessionData.lastAccessed = timestamp;
      }
    }
  }

  /**
   * Destroy a session
   */
  async destroySession(conversationId) {
    if (!conversationId) return false;

    if (redisService.isAvailable()) {
      const sessionKey = config.keys.session(conversationId);
      const conversationKey = config.keys.conversation(conversationId);
      
      // Remove session and conversation data
      await Promise.all([
        redisService.del(sessionKey),
        redisService.del(conversationKey),
        this.removeFromActiveIndex(conversationId)
      ]);
    } else {
      // Fallback to in-memory
      this.activeSessions.delete(conversationId);
    }

    console.log(`Destroyed session: ${conversationId}`);
    return true;
  }

  /**
   * Get session information
   */
  async getSessionInfo(conversationId) {
    const validation = await this.validateSession(conversationId);
    
    if (!validation.valid) {
      return null;
    }

    return {
      id: conversationId,
      ...validation.sessionData,
      storageType: redisService.isAvailable() ? 'redis' : 'memory'
    };
  }

  /**
   * List active sessions (for monitoring/debugging)
   */
  async getActiveSessions() {
    if (redisService.isAvailable()) {
      try {
        const sessionKeys = await redisService.keys(config.keys.session('*'));
        const sessions = [];

        for (const key of sessionKeys) {
          const sessionData = await redisService.get(key);
          if (sessionData) {
            sessions.push({
              id: sessionData.id,
              createdAt: sessionData.createdAt,
              lastAccessed: sessionData.lastAccessed,
              status: sessionData.status
            });
          }
        }

        return sessions;
      } catch (error) {
        console.error('Error getting active sessions from Redis:', error);
        return [];
      }
    } else {
      // Fallback to in-memory
      return Array.from(this.activeSessions.values()).map(session => ({
        id: session.id,
        createdAt: session.createdAt,
        lastAccessed: session.lastAccessed,
        status: session.status
      }));
    }
  }

  /**
   * Add session to active index (for cleanup purposes)
   */
  async addToActiveIndex(conversationId) {
    if (redisService.isAvailable()) {
      try {
        const timestamp = Date.now();
        await redisService.client.zadd(config.keys.activeConversations, timestamp, conversationId);
      } catch (error) {
        console.error('Error adding to active index:', error);
      }
    }
  }

  /**
   * Remove session from active index
   */
  async removeFromActiveIndex(conversationId) {
    if (redisService.isAvailable()) {
      try {
        await redisService.client.zrem(config.keys.activeConversations, conversationId);
      } catch (error) {
        console.error('Error removing from active index:', error);
      }
    }
  }

  /**
   * Get oldest sessions for cleanup
   */
  async getOldestSessions(count = 10) {
    if (redisService.isAvailable()) {
      try {
        // Get oldest sessions from sorted set
        const oldestIds = await redisService.client.zrange(
          config.keys.activeConversations, 
          0, 
          count - 1,
          'WITHSCORES'
        );
        
        const sessions = [];
        for (let i = 0; i < oldestIds.length; i += 2) {
          const conversationId = oldestIds[i];
          const timestamp = oldestIds[i + 1];
          sessions.push({
            conversationId,
            timestamp: new Date(parseInt(timestamp))
          });
        }
        
        return sessions;
      } catch (error) {
        console.error('Error getting oldest sessions:', error);
        return [];
      }
    }
    
    return [];
  }

  /**
   * Clean up expired sessions manually
   */
  async cleanupExpiredSessions() {
    const now = Date.now();
    const maxAge = config.redis.defaultTTL * 1000;
    
    if (redisService.isAvailable()) {
      try {
        // Remove sessions older than maxAge from the sorted set
        const cutoffTime = now - maxAge;
        const expiredIds = await redisService.client.zrangebyscore(
          config.keys.activeConversations,
          '-inf',
          cutoffTime
        );
        
        if (expiredIds.length > 0) {
          console.log(`Cleaning up ${expiredIds.length} expired sessions`);
          
          for (const conversationId of expiredIds) {
            await this.destroySession(conversationId);
          }
        }
        
        return expiredIds.length;
      } catch (error) {
        console.error('Error during cleanup:', error);
        return 0;
      }
    } else {
      // Cleanup in-memory sessions
      let cleanedCount = 0;
      for (const [id, session] of this.activeSessions.entries()) {
        const sessionAge = now - new Date(session.lastAccessed).getTime();
        if (sessionAge > maxAge) {
          this.activeSessions.delete(id);
          cleanedCount++;
        }
      }
      
      if (cleanedCount > 0) {
        console.log(`Cleaned up ${cleanedCount} expired in-memory sessions`);
      }
      
      return cleanedCount;
    }
  }

  /**
   * Get session statistics
   */
  async getSessionStats() {
    const activeSessions = await this.getActiveSessions();
    const now = new Date();
    
    const stats = {
      total: activeSessions.length,
      storage: redisService.isAvailable() ? 'redis' : 'memory',
      redisStatus: redisService.getStatus(),
      recentSessions: 0,
      oldSessions: 0
    };

    // Categorize sessions by age
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    
    for (const session of activeSessions) {
      const lastAccessed = new Date(session.lastAccessed);
      if (lastAccessed > oneHourAgo) {
        stats.recentSessions++;
      } else {
        stats.oldSessions++;
      }
    }

    return stats;
  }
}

// Create singleton instance
const sessionManager = new SessionManager();

module.exports = sessionManager; 