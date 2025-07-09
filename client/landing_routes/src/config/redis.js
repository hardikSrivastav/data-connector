const config = {
  development: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
    password: process.env.REDIS_PASSWORD || undefined,
    db: process.env.REDIS_DB || 0,
    retryDelayOnFailover: 100,
    retryDelayOnClusterDown: 300,
    maxRetriesPerRequest: 3,
    lazyConnect: true,
    keepAlive: 30000,
    // TTL settings
    defaultTTL: 48 * 60 * 60, // 48 hours in seconds
    extendTTL: 24 * 60 * 60,  // 24 hours extension on activity
  },
  
  production: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
    password: process.env.REDIS_PASSWORD,
    db: process.env.REDIS_DB || 0,
    retryDelayOnFailover: 100,
    retryDelayOnClusterDown: 300,
    maxRetriesPerRequest: 3,
    lazyConnect: true,
    keepAlive: 30000,
    // Production TTL settings (shorter for resource management)
    defaultTTL: 24 * 60 * 60, // 24 hours in seconds
    extendTTL: 12 * 60 * 60,  // 12 hours extension on activity
  }
};

const environment = process.env.NODE_ENV || 'development';

module.exports = {
  redis: config[environment],
  environment,
  
  // Key patterns for Redis
  keys: {
    conversation: (id) => `chat:conversation:${id}`,
    session: (id) => `chat:session:${id}`,
    activeConversations: 'chat:active:conversations',
    conversationIndex: 'chat:index:conversations'
  },
  
  // Feature flags
  features: {
    enableRedis: process.env.ENABLE_REDIS !== 'false',
    enableCleanup: process.env.ENABLE_CLEANUP !== 'false',
    enableMonitoring: process.env.ENABLE_REDIS_MONITORING === 'true'
  }
}; 