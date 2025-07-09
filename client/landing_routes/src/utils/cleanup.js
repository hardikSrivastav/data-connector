const cron = require('node-cron');
const sessionManager = require('../services/sessionManager');
const conversationStorage = require('../services/conversationStorage');
const redisService = require('../services/redisService');
const config = require('../config/redis');
const fs = require('fs').promises;
const path = require('path');

class CleanupManager {
  constructor() {
    this.cleanupTasks = [];
    this.isRunning = false;
  }

  /**
   * Initialize cleanup tasks
   */
  initialize() {
    if (!config.features.enableCleanup) {
      console.log('Cleanup disabled by configuration');
      return;
    }

    console.log('Initializing cleanup tasks...');

    // Cleanup expired sessions every hour
    const sessionCleanupTask = cron.schedule('0 * * * *', async () => {
      await this.cleanupExpiredSessions();
    }, {
      scheduled: false,
      name: 'session-cleanup'
    });

    // Cleanup old conversations every 6 hours
    const conversationCleanupTask = cron.schedule('0 */6 * * *', async () => {
      await this.cleanupOldConversations();
    }, {
      scheduled: false,
      name: 'conversation-cleanup'
    });

    // Cleanup deployment packages every 12 hours
    const deploymentCleanupTask = cron.schedule('0 */12 * * *', async () => {
      await this.cleanupDeploymentPackages();
    }, {
      scheduled: false,
      name: 'deployment-cleanup'
    });

    // Health check log every 30 minutes
    const healthCheckTask = cron.schedule('*/30 * * * *', async () => {
      await this.logSystemHealth();
    }, {
      scheduled: false,
      name: 'health-check'
    });

    this.cleanupTasks = [
      sessionCleanupTask,
      conversationCleanupTask,
      deploymentCleanupTask,
      healthCheckTask
    ];

    console.log(`Initialized ${this.cleanupTasks.length} cleanup tasks`);
  }

  /**
   * Start all cleanup tasks
   */
  start() {
    if (this.isRunning) {
      console.log('Cleanup tasks already running');
      return;
    }

    console.log('Starting cleanup tasks...');
    this.cleanupTasks.forEach(task => {
      task.start();
    });
    this.isRunning = true;
    console.log('Cleanup tasks started');
  }

  /**
   * Stop all cleanup tasks
   */
  stop() {
    if (!this.isRunning) {
      console.log('Cleanup tasks not running');
      return;
    }

    console.log('Stopping cleanup tasks...');
    this.cleanupTasks.forEach(task => {
      task.stop();
    });
    this.isRunning = false;
    console.log('Cleanup tasks stopped');
  }

  /**
   * Clean up expired sessions
   */
  async cleanupExpiredSessions() {
    try {
      console.log('Running session cleanup...');
      const cleaned = await sessionManager.cleanupExpiredSessions();
      
      if (cleaned > 0) {
        console.log(`Cleaned up ${cleaned} expired sessions`);
        this.logCleanupActivity('sessions', cleaned);
      }
      
      return cleaned;
    } catch (error) {
      console.error('Error during session cleanup:', error);
      return 0;
    }
  }

  /**
   * Clean up old conversations
   */
  async cleanupOldConversations() {
    try {
      console.log('Running conversation cleanup...');
      const cleaned = await conversationStorage.cleanupOldConversations();
      
      if (cleaned > 0) {
        console.log(`Cleaned up ${cleaned} old conversations`);
        this.logCleanupActivity('conversations', cleaned);
      }
      
      return cleaned;
    } catch (error) {
      console.error('Error during conversation cleanup:', error);
      return 0;
    }
  }

  /**
   * Clean up deployment package directories for expired conversations
   */
  async cleanupDeploymentPackages() {
    try {
      console.log('Running deployment package cleanup...');
      const deployPackagesDir = path.join(__dirname, '../../deploy-packages');
      
      let cleaned = 0;
      
      try {
        const entries = await fs.readdir(deployPackagesDir);
        
        for (const entry of entries) {
          const entryPath = path.join(deployPackagesDir, entry);
          const stat = await fs.stat(entryPath);
          
          if (stat.isDirectory()) {
            // Check if this conversation still exists
            const conversationExists = await conversationStorage.conversationExists(entry);
            
            if (!conversationExists) {
              // Remove the directory
              await fs.rmdir(entryPath, { recursive: true });
              console.log(`Removed deployment package directory: ${entry}`);
              cleaned++;
            }
          }
        }
      } catch (error) {
        if (error.code !== 'ENOENT') {
          throw error;
        }
        // deploy-packages directory doesn't exist yet, which is fine
      }
      
      if (cleaned > 0) {
        console.log(`Cleaned up ${cleaned} deployment package directories`);
        this.logCleanupActivity('deployment-packages', cleaned);
      }
      
      return cleaned;
    } catch (error) {
      console.error('Error during deployment package cleanup:', error);
      return 0;
    }
  }

  /**
   * Log system health periodically
   */
  async logSystemHealth() {
    try {
      const redisStatus = redisService.getStatus();
      const sessionStats = await sessionManager.getSessionStats();
      const storageStats = await conversationStorage.getStorageStats();
      
      const healthInfo = {
        timestamp: new Date().toISOString(),
        redis: redisStatus,
        sessions: sessionStats,
        storage: storageStats
      };
      
      console.log('System Health Check:', JSON.stringify(healthInfo, null, 2));
      
      // Log to file if needed
      await this.logHealthToFile(healthInfo);
      
    } catch (error) {
      console.error('Error during health check:', error);
    }
  }

  /**
   * Log cleanup activity to file
   */
  async logCleanupActivity(type, count) {
    try {
      const logEntry = {
        timestamp: new Date().toISOString(),
        type: type,
        cleaned: count
      };
      
      const logPath = path.join(__dirname, '../../logs/cleanup.log');
      const logLine = JSON.stringify(logEntry) + '\n';
      
      await fs.appendFile(logPath, logLine);
    } catch (error) {
      console.error('Error logging cleanup activity:', error);
    }
  }

  /**
   * Log health information to file
   */
  async logHealthToFile(healthInfo) {
    try {
      const logPath = path.join(__dirname, '../../logs/health.log');
      const logLine = JSON.stringify(healthInfo) + '\n';
      
      await fs.appendFile(logPath, logLine);
    } catch (error) {
      console.error('Error logging health info:', error);
    }
  }

  /**
   * Manual cleanup of all types
   */
  async cleanupAll() {
    console.log('Starting manual cleanup of all types...');
    
    const results = {
      sessions: await this.cleanupExpiredSessions(),
      conversations: await this.cleanupOldConversations(),
      deploymentPackages: await this.cleanupDeploymentPackages()
    };
    
    console.log('Manual cleanup completed:', results);
    return results;
  }

  /**
   * Get cleanup statistics
   */
  getStats() {
    return {
      isRunning: this.isRunning,
      tasksCount: this.cleanupTasks.length,
      tasks: this.cleanupTasks.map(task => ({
        name: task.options.name,
        running: task.running
      })),
      cleanupEnabled: config.features.enableCleanup
    };
  }
}

// Create singleton instance
const cleanupManager = new CleanupManager();

// Initialize cleanup tasks when module is loaded
cleanupManager.initialize();

// Graceful shutdown handling
process.on('SIGINT', () => {
  console.log('Received SIGINT, stopping cleanup tasks...');
  cleanupManager.stop();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, stopping cleanup tasks...');
  cleanupManager.stop();
  process.exit(0);
});

module.exports = cleanupManager; 