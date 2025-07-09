const redisService = require('./redisService');
const sessionManager = require('./sessionManager');
const config = require('../config/redis');

class ConversationStorage {
  constructor() {
    this.conversations = new Map(); // Fallback storage when Redis unavailable
  }

  /**
   * Save a conversation to storage
   */
  async saveConversation(conversationId, conversationData) {
    if (!conversationId || !conversationData) {
      throw new Error('conversationId and conversationData are required');
    }

    // Ensure we have the basic required fields
    const dataToStore = {
      id: conversationId,
      userInfo: conversationData.userInfo || {},
      messages: conversationData.messages || [],
      extractedConfig: conversationData.extractedConfig || {},
      systemPrompt: conversationData.systemPrompt || '',
      createdAt: conversationData.createdAt || new Date(),
      lastUpdated: new Date(),
      generatedPackage: conversationData.generatedPackage || null,
      deploymentPath: conversationData.deploymentPath || null,
      ...conversationData
    };

    try {
      if (redisService.isAvailable()) {
        const conversationKey = config.keys.conversation(conversationId);
        const success = await redisService.set(
          conversationKey, 
          dataToStore, 
          config.redis.defaultTTL
        );
        
        if (success) {
          // Also update session last accessed time
          await sessionManager.updateLastAccessed(conversationId);
          console.log(`Saved conversation ${conversationId} to Redis`);
          return true;
        } else {
          console.warn(`Failed to save conversation ${conversationId} to Redis, falling back to memory`);
          this.conversations.set(conversationId, dataToStore);
          return true;
        }
      } else {
        // Fallback to in-memory storage
        this.conversations.set(conversationId, dataToStore);
        console.log(`Saved conversation ${conversationId} to memory (Redis unavailable)`);
        return true;
      }
    } catch (error) {
      console.error(`Error saving conversation ${conversationId}:`, error);
      // Fallback to memory even on error
      this.conversations.set(conversationId, dataToStore);
      return false;
    }
  }

  /**
   * Load a conversation from storage
   */
  async loadConversation(conversationId) {
    if (!conversationId) {
      return null;
    }

    try {
      let conversationData = null;

      if (redisService.isAvailable()) {
        const conversationKey = config.keys.conversation(conversationId);
        conversationData = await redisService.get(conversationKey);
        
        if (conversationData) {
          // Extend TTL on access
          await redisService.expire(conversationKey, config.redis.extendTTL);
          await sessionManager.updateLastAccessed(conversationId);
          console.log(`Loaded conversation ${conversationId} from Redis`);
        }
      }

      // Fallback to in-memory if not found in Redis
      if (!conversationData) {
        conversationData = this.conversations.get(conversationId);
        if (conversationData) {
          console.log(`Loaded conversation ${conversationId} from memory`);
        }
      }

      return conversationData;
    } catch (error) {
      console.error(`Error loading conversation ${conversationId}:`, error);
      // Try fallback to memory
      return this.conversations.get(conversationId) || null;
    }
  }

  /**
   * Check if a conversation exists
   */
  async conversationExists(conversationId) {
    if (!conversationId) {
      return false;
    }

    try {
      if (redisService.isAvailable()) {
        const conversationKey = config.keys.conversation(conversationId);
        return await redisService.exists(conversationKey);
      } else {
        return this.conversations.has(conversationId);
      }
    } catch (error) {
      console.error(`Error checking conversation existence ${conversationId}:`, error);
      return this.conversations.has(conversationId);
    }
  }

  /**
   * Delete a conversation from storage
   */
  async deleteConversation(conversationId) {
    if (!conversationId) {
      return false;
    }

    try {
      let deleted = false;

      if (redisService.isAvailable()) {
        const conversationKey = config.keys.conversation(conversationId);
        deleted = await redisService.del(conversationKey);
        
        if (deleted) {
          console.log(`Deleted conversation ${conversationId} from Redis`);
        }
      }

      // Also remove from memory (in case it exists there)
      const memoryDeleted = this.conversations.delete(conversationId);
      
      if (memoryDeleted && !deleted) {
        console.log(`Deleted conversation ${conversationId} from memory`);
        deleted = true;
      }

      return deleted;
    } catch (error) {
      console.error(`Error deleting conversation ${conversationId}:`, error);
      // Try to delete from memory at least
      return this.conversations.delete(conversationId);
    }
  }

  /**
   * Update specific fields of a conversation
   */
  async updateConversation(conversationId, updates) {
    if (!conversationId || !updates) {
      return false;
    }

    try {
      const existingData = await this.loadConversation(conversationId);
      
      if (!existingData) {
        console.warn(`Cannot update non-existent conversation ${conversationId}`);
        return false;
      }

      const updatedData = {
        ...existingData,
        ...updates,
        lastUpdated: new Date()
      };

      return await this.saveConversation(conversationId, updatedData);
    } catch (error) {
      console.error(`Error updating conversation ${conversationId}:`, error);
      return false;
    }
  }

  /**
   * Add a message to a conversation
   */
  async addMessage(conversationId, message) {
    if (!conversationId || !message) {
      return false;
    }

    try {
      const conversationData = await this.loadConversation(conversationId);
      
      if (!conversationData) {
        console.warn(`Cannot add message to non-existent conversation ${conversationId}`);
        return false;
      }

      const updatedMessages = [...(conversationData.messages || []), {
        ...message,
        timestamp: message.timestamp || new Date()
      }];

      return await this.updateConversation(conversationId, {
        messages: updatedMessages
      });
    } catch (error) {
      console.error(`Error adding message to conversation ${conversationId}:`, error);
      return false;
    }
  }

  /**
   * Update extracted configuration
   */
  async updateExtractedConfig(conversationId, extractedConfig) {
    return await this.updateConversation(conversationId, {
      extractedConfig: extractedConfig
    });
  }

  /**
   * Update generated package info
   */
  async updateGeneratedPackage(conversationId, generatedPackage, deploymentPath = null) {
    return await this.updateConversation(conversationId, {
      generatedPackage: generatedPackage,
      deploymentPath: deploymentPath
    });
  }

  /**
   * Get conversation metadata (without messages for performance)
   */
  async getConversationMetadata(conversationId) {
    const conversationData = await this.loadConversation(conversationId);
    
    if (!conversationData) {
      return null;
    }

    return {
      id: conversationData.id,
      userInfo: conversationData.userInfo,
      extractedConfig: conversationData.extractedConfig,
      createdAt: conversationData.createdAt,
      lastUpdated: conversationData.lastUpdated,
      messageCount: conversationData.messages ? conversationData.messages.length : 0,
      hasGeneratedPackage: !!conversationData.generatedPackage,
      deploymentPath: conversationData.deploymentPath,
      storageType: redisService.isAvailable() ? 'redis' : 'memory'
    };
  }

  /**
   * List all conversations (metadata only)
   */
  async listConversations() {
    try {
      const conversations = [];

      if (redisService.isAvailable()) {
        const conversationKeys = await redisService.keys(config.keys.conversation('*'));
        
        for (const key of conversationKeys) {
          const conversationId = key.split(':').pop(); // Extract ID from key
          const metadata = await this.getConversationMetadata(conversationId);
          if (metadata) {
            conversations.push(metadata);
          }
        }
      } else {
        // Fallback to in-memory
        for (const [conversationId, data] of this.conversations.entries()) {
          conversations.push({
            id: conversationId,
            userInfo: data.userInfo,
            extractedConfig: data.extractedConfig,
            createdAt: data.createdAt,
            lastUpdated: data.lastUpdated,
            messageCount: data.messages ? data.messages.length : 0,
            hasGeneratedPackage: !!data.generatedPackage,
            deploymentPath: data.deploymentPath,
            storageType: 'memory'
          });
        }
      }

      return conversations;
    } catch (error) {
      console.error('Error listing conversations:', error);
      return [];
    }
  }

  /**
   * Get storage statistics
   */
  async getStorageStats() {
    try {
      const conversations = await this.listConversations();
      const now = new Date();
      
      const stats = {
        totalConversations: conversations.length,
        storageType: redisService.isAvailable() ? 'redis' : 'memory',
        redisStatus: redisService.getStatus(),
        memoryConversations: this.conversations.size,
        recentConversations: 0,
        oldConversations: 0,
        conversationsWithPackages: 0
      };

      // Analyze conversation data
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
      
      for (const conversation of conversations) {
        const lastUpdated = new Date(conversation.lastUpdated);
        
        if (lastUpdated > oneHourAgo) {
          stats.recentConversations++;
        } else {
          stats.oldConversations++;
        }
        
        if (conversation.hasGeneratedPackage) {
          stats.conversationsWithPackages++;
        }
      }

      return stats;
    } catch (error) {
      console.error('Error getting storage stats:', error);
      return {
        totalConversations: 0,
        storageType: 'error',
        error: error.message
      };
    }
  }

  /**
   * Migrate conversation from memory to Redis (utility function)
   */
  async migrateToRedis(conversationId) {
    if (redisService.isAvailable() && this.conversations.has(conversationId)) {
      const conversationData = this.conversations.get(conversationId);
      const conversationKey = config.keys.conversation(conversationId);
      
      const success = await redisService.set(
        conversationKey, 
        conversationData, 
        config.redis.defaultTTL
      );
      
      if (success) {
        console.log(`Migrated conversation ${conversationId} to Redis`);
        return true;
      }
    }
    
    return false;
  }

  /**
   * Cleanup old conversations manually
   */
  async cleanupOldConversations(maxAge = null) {
    const ageLimit = maxAge || (config.redis.defaultTTL * 1000);
    const now = Date.now();
    let cleanedCount = 0;

    try {
      const conversations = await this.listConversations();
      
      for (const conversation of conversations) {
        const age = now - new Date(conversation.lastUpdated).getTime();
        
        if (age > ageLimit) {
          const deleted = await this.deleteConversation(conversation.id);
          if (deleted) {
            cleanedCount++;
            console.log(`Cleaned up old conversation: ${conversation.id}`);
          }
        }
      }

      console.log(`Cleanup completed: removed ${cleanedCount} old conversations`);
      return cleanedCount;
    } catch (error) {
      console.error('Error during conversation cleanup:', error);
      return 0;
    }
  }
}

// Create singleton instance
const conversationStorage = new ConversationStorage();

module.exports = conversationStorage; 