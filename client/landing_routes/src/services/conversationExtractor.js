/**
 * Conversation Extractor - Intelligently extracts deployment requirements from conversations
 * Uses pattern matching and context analysis to build deployment configuration
 */
class ConversationExtractor {
  constructor() {
    this.extractionPatterns = this.initializePatterns();
    this.contextKeywords = this.initializeContextKeywords();
  }

  /**
   * Extract deployment configuration from conversation messages
   */
  extractFromConversation(messages, currentConfig = {}) {
    // Initialize extraction result
    const extraction = {
      databases: currentConfig.databases || {},
      authentication: currentConfig.authentication || {},
      deployment: currentConfig.deployment || {},
      confidence: {},
      extractedFromMessage: {}
    };

    // Process each message for extraction opportunities
    for (let i = 0; i < messages.length; i++) {
      const message = messages[i];
      if (message.role === 'user') {
        const messageExtractions = this.extractFromMessage(message.content, i);
        this.mergeExtractions(extraction, messageExtractions, i);
      }
    }

    // Calculate confidence scores
    this.calculateConfidence(extraction);

    // Validate extracted data
    this.validateExtractions(extraction);

    return extraction;
  }

  /**
   * Extract information from a single message
   */
  extractFromMessage(messageContent, messageIndex) {
    const content = messageContent.toLowerCase();
    const extraction = {
      databases: {},
      authentication: {},
      deployment: {},
      raw_content: messageContent
    };

    // Database extraction
    this.extractDatabaseInfo(content, extraction, messageContent);

    // Authentication extraction
    this.extractAuthenticationInfo(content, extraction, messageContent);

    // Deployment configuration extraction
    this.extractDeploymentInfo(content, extraction, messageContent);

    return extraction;
  }

  /**
   * Extract database configuration information
   */
  extractDatabaseInfo(content, extraction, originalContent) {
    // PostgreSQL extraction
    if (this.matchesPattern(content, 'postgresql')) {
      extraction.databases.postgresql = extraction.databases.postgresql || {};
      
      // Host extraction
      const hostMatch = this.extractHost(originalContent, ['postgres', 'pg']);
      if (hostMatch) extraction.databases.postgresql.host = hostMatch;
      
      // Port extraction
      const portMatch = this.extractPort(originalContent, 5432);
      if (portMatch) extraction.databases.postgresql.port = portMatch;
      
      // Database name extraction
      const dbMatch = this.extractDatabaseName(originalContent);
      if (dbMatch) extraction.databases.postgresql.database = dbMatch;
      
      // Credentials extraction
      const credentials = this.extractCredentials(originalContent);
      if (credentials.username) extraction.databases.postgresql.username = credentials.username;
      if (credentials.password) extraction.databases.postgresql.password = credentials.password;
      
      // SSL detection
      if (content.includes('ssl') || content.includes('secure')) {
        extraction.databases.postgresql.ssl_enabled = true;
      }
    }

    // MongoDB extraction
    if (this.matchesPattern(content, 'mongodb')) {
      extraction.databases.mongodb = extraction.databases.mongodb || {};
      
      const hostMatch = this.extractHost(originalContent, ['mongo', 'mongodb']);
      if (hostMatch) extraction.databases.mongodb.host = hostMatch;
      
      const portMatch = this.extractPort(originalContent, 27017);
      if (portMatch) extraction.databases.mongodb.port = portMatch;
      
      const dbMatch = this.extractDatabaseName(originalContent);
      if (dbMatch) extraction.databases.mongodb.database = dbMatch;
      
      const credentials = this.extractCredentials(originalContent);
      if (credentials.username) extraction.databases.mongodb.username = credentials.username;
      if (credentials.password) extraction.databases.mongodb.password = credentials.password;
      
      // Auth source detection
      const authSourceMatch = originalContent.match(/auth[_\s]?source[:\s]+([^\s,]+)/i);
      if (authSourceMatch) {
        extraction.databases.mongodb.auth_source = authSourceMatch[1];
      }
    }

    // Qdrant extraction
    if (this.matchesPattern(content, 'qdrant')) {
      extraction.databases.qdrant = extraction.databases.qdrant || {};
      
      const hostMatch = this.extractHost(originalContent, ['qdrant', 'vector']);
      if (hostMatch) extraction.databases.qdrant.host = hostMatch;
      
      const portMatch = this.extractPort(originalContent, 6333);
      if (portMatch) extraction.databases.qdrant.port = portMatch;
      
      // API key extraction
      const apiKeyMatch = this.extractApiKey(originalContent, 'qdrant');
      if (apiKeyMatch) extraction.databases.qdrant.api_key = apiKeyMatch;
    }
  }

  /**
   * Extract authentication configuration
   */
  extractAuthenticationInfo(content, extraction, originalContent) {
    // Provider detection
    if (this.matchesPattern(content, 'google')) {
      extraction.authentication.provider = 'google';
      
      // Google-specific extractions
      const clientIdMatch = originalContent.match(/client[_\s]?id[:\s]+([^\s,]+)/i);
      if (clientIdMatch) extraction.authentication.client_id = clientIdMatch[1];
      
      const clientSecretMatch = originalContent.match(/client[_\s]?secret[:\s]+([^\s,]+)/i);
      if (clientSecretMatch) extraction.authentication.client_secret = clientSecretMatch[1];
      
      const domainMatch = originalContent.match(/domain[:\s]+([a-zA-Z0-9.-]+)/i);
      if (domainMatch) extraction.authentication.domain = domainMatch[1];
    }

    if (this.matchesPattern(content, 'okta')) {
      extraction.authentication.provider = 'okta';
      
      // Okta domain extraction
      const oktaDomainMatch = originalContent.match(/([a-zA-Z0-9-]+\.okta\.com)/i);
      if (oktaDomainMatch) extraction.authentication.okta_domain = oktaDomainMatch[1];
      
      const clientIdMatch = originalContent.match(/client[_\s]?id[:\s]+([^\s,]+)/i);
      if (clientIdMatch) extraction.authentication.client_id = clientIdMatch[1];
      
      const clientSecretMatch = originalContent.match(/client[_\s]?secret[:\s]+([^\s,]+)/i);
      if (clientSecretMatch) extraction.authentication.client_secret = clientSecretMatch[1];
    }

    if (this.matchesPattern(content, 'azure')) {
      extraction.authentication.provider = 'azure';
      
      const tenantIdMatch = originalContent.match(/tenant[_\s]?id[:\s]+([^\s,]+)/i);
      if (tenantIdMatch) extraction.authentication.tenant_id = tenantIdMatch[1];
      
      const clientIdMatch = originalContent.match(/client[_\s]?id[:\s]+([^\s,]+)/i);
      if (clientIdMatch) extraction.authentication.client_id = clientIdMatch[1];
    }

    // Role mappings extraction
    const roleMatch = this.extractRoleMappings(originalContent);
    if (roleMatch) extraction.authentication.role_mappings = roleMatch;
  }

  /**
   * Extract deployment configuration
   */
  extractDeploymentInfo(content, extraction, originalContent) {
    // Environment detection
    if (content.includes('production') || content.includes('prod')) {
      extraction.deployment.environment = 'production';
    } else if (content.includes('development') || content.includes('dev')) {
      extraction.deployment.environment = 'development';
    } else if (content.includes('staging') || content.includes('stage')) {
      extraction.deployment.environment = 'staging';
    }

    // LLM provider detection
    if (content.includes('openai') || content.includes('gpt')) {
      extraction.deployment.llm_provider = 'openai';
    } else if (content.includes('anthropic') || content.includes('claude')) {
      extraction.deployment.llm_provider = 'anthropic';
    }

    // Domain extraction
    const domainMatch = originalContent.match(/(?:https?:\/\/)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
    if (domainMatch && !domainMatch[1].includes('example') && !domainMatch[1].includes('your')) {
      extraction.deployment.domain_name = domainMatch[1];
    }

    // API key extraction
    const apiKeyMatch = this.extractApiKey(originalContent, 'llm');
    if (apiKeyMatch) extraction.deployment.api_key = apiKeyMatch;

    // Team size extraction
    const teamSizeMatch = originalContent.match(/(\d+)\s*(?:people|users|team|members)/i);
    if (teamSizeMatch) {
      extraction.deployment.team_size = parseInt(teamSizeMatch[1]);
    }

    // Custom networks extraction
    if (content.includes('network') || content.includes('join')) {
      const networkMatch = originalContent.match(/network[s]?[:\s]+([^\s,]+)/i);
      if (networkMatch) {
        extraction.deployment.custom_networks = [networkMatch[1]];
      }
    }

    // Host mappings extraction
    const hostMappingMatch = this.extractHostMappings(originalContent);
    if (hostMappingMatch) {
      extraction.deployment.host_mappings = hostMappingMatch;
    }
  }

  /**
   * Helper method to extract host information
   */
  extractHost(content, contexts = []) {
    // Try specific context-based patterns first
    for (const context of contexts) {
      const contextPattern = new RegExp(`${context}[^\\s]*[\\s]*(?:host|server|url)[:\\s]+([^\\s,;]+)`, 'i');
      const match = content.match(contextPattern);
      if (match) return match[1];
    }

    // Try general host patterns
    const hostPatterns = [
      /host[:\s]+([^\s,;]+)/i,
      /server[:\s]+([^\s,;]+)/i,
      /([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):?\d*/i
    ];

    for (const pattern of hostPatterns) {
      const match = content.match(pattern);
      if (match && !match[1].includes('your') && !match[1].includes('example')) {
        return match[1];
      }
    }

    return null;
  }

  /**
   * Extract port information with fallback to default
   */
  extractPort(content, defaultPort) {
    const portMatch = content.match(/:(\d{4,5})/);
    if (portMatch) {
      return parseInt(portMatch[1]);
    }

    const explicitPortMatch = content.match(/port[:\s]+(\d+)/i);
    if (explicitPortMatch) {
      return parseInt(explicitPortMatch[1]);
    }

    return defaultPort;
  }

  /**
   * Extract database name
   */
  extractDatabaseName(content) {
    const dbNamePatterns = [
      /database[:\s]+([^\s,;]+)/i,
      /db[:\s]+([^\s,;]+)/i,
      /\/([a-zA-Z_][a-zA-Z0-9_]*)\??/
    ];

    for (const pattern of dbNamePatterns) {
      const match = content.match(pattern);
      if (match && !match[1].includes('your') && !match[1].includes('example')) {
        return match[1];
      }
    }

    return null;
  }

  /**
   * Extract credentials from content
   */
  extractCredentials(content) {
    const credentials = {};

    // Username patterns
    const usernamePatterns = [
      /username[:\s]+([^\s,;]+)/i,
      /user[:\s]+([^\s,;]+)/i,
      /([a-zA-Z_][a-zA-Z0-9_]*):([^\s@,;]+)@/
    ];

    for (const pattern of usernamePatterns) {
      const match = content.match(pattern);
      if (match) {
        credentials.username = match[1];
        break;
      }
    }

    // Password patterns
    const passwordPatterns = [
      /password[:\s]+([^\s,;]+)/i,
      /pass[:\s]+([^\s,;]+)/i
    ];

    for (const pattern of passwordPatterns) {
      const match = content.match(pattern);
      if (match) {
        credentials.password = match[1];
        break;
      }
    }

    return credentials;
  }

  /**
   * Extract API keys
   */
  extractApiKey(content, context) {
    const apiKeyPatterns = [
      new RegExp(`${context}[\\s_-]*api[\\s_-]*key[:\\s]+([^\\s,;]+)`, 'i'),
      /api[_\s]?key[:\s]+([^\s,;]+)/i,
      /key[:\s]+([a-zA-Z0-9_-]{20,})/i
    ];

    for (const pattern of apiKeyPatterns) {
      const match = content.match(pattern);
      if (match && !match[1].includes('your') && !match[1].includes('example')) {
        return match[1];
      }
    }

    return null;
  }

  /**
   * Extract role mappings
   */
  extractRoleMappings(content) {
    // Look for group to role mapping patterns
    const mappingPattern = /([a-zA-Z\s]+)\s*(?:maps?\s*to|->|:)\s*([a-zA-Z]+)/gi;
    const mappings = {};
    let match;

    while ((match = mappingPattern.exec(content)) !== null) {
      const group = match[1].trim();
      const role = match[2].trim();
      mappings[group] = role;
    }

    return Object.keys(mappings).length > 0 ? mappings : null;
  }

  /**
   * Extract host mappings for DNS resolution
   */
  extractHostMappings(content) {
    const mappingPattern = /([a-zA-Z0-9.-]+)\s*(?:maps?\s*to|->|:)\s*(\d+\.\d+\.\d+\.\d+)/gi;
    const mappings = {};
    let match;

    while ((match = mappingPattern.exec(content)) !== null) {
      mappings[match[1]] = match[2];
    }

    return Object.keys(mappings).length > 0 ? mappings : null;
  }

  /**
   * Check if content matches a pattern for a specific technology
   */
  matchesPattern(content, technology) {
    const patterns = this.extractionPatterns[technology] || [];
    return patterns.some(pattern => content.includes(pattern));
  }

  /**
   * Merge new extractions with existing configuration
   */
  mergeExtractions(currentExtraction, newExtraction, messageIndex) {
    // Merge databases
    for (const [dbType, dbConfig] of Object.entries(newExtraction.databases)) {
      if (!currentExtraction.databases[dbType]) {
        currentExtraction.databases[dbType] = {};
      }
      Object.assign(currentExtraction.databases[dbType], dbConfig);
      currentExtraction.extractedFromMessage[`databases.${dbType}`] = messageIndex;
    }

    // Merge authentication
    Object.assign(currentExtraction.authentication, newExtraction.authentication);
    if (Object.keys(newExtraction.authentication).length > 0) {
      currentExtraction.extractedFromMessage['authentication'] = messageIndex;
    }

    // Merge deployment
    Object.assign(currentExtraction.deployment, newExtraction.deployment);
    if (Object.keys(newExtraction.deployment).length > 0) {
      currentExtraction.extractedFromMessage['deployment'] = messageIndex;
    }
  }

  /**
   * Calculate confidence scores for extracted information
   */
  calculateConfidence(extraction) {
    extraction.confidence = {
      databases: this.calculateDatabaseConfidence(extraction.databases),
      authentication: this.calculateAuthConfidence(extraction.authentication),
      deployment: this.calculateDeploymentConfidence(extraction.deployment),
      overall: 0
    };

    // Calculate overall confidence
    const confidenceValues = Object.values(extraction.confidence).filter(v => typeof v === 'number');
    extraction.confidence.overall = confidenceValues.length > 0 
      ? confidenceValues.reduce((a, b) => a + b, 0) / confidenceValues.length 
      : 0;
  }

  calculateDatabaseConfidence(databases) {
    if (Object.keys(databases).length === 0) return 0;

    let total = 0;
    let count = 0;

    for (const [dbType, config] of Object.entries(databases)) {
      let dbConfidence = 0;
      if (config.host) dbConfidence += 0.4;
      if (config.port) dbConfidence += 0.2;
      if (config.database) dbConfidence += 0.2;
      if (config.username) dbConfidence += 0.1;
      if (config.password) dbConfidence += 0.1;

      total += dbConfidence;
      count++;
    }

    return count > 0 ? total / count : 0;
  }

  calculateAuthConfidence(auth) {
    if (!auth.provider) return 0;

    let confidence = 0.3; // Base for having a provider
    if (auth.client_id) confidence += 0.3;
    if (auth.client_secret) confidence += 0.3;
    if (auth.domain || auth.okta_domain || auth.tenant_id) confidence += 0.1;

    return confidence;
  }

  calculateDeploymentConfidence(deployment) {
    let confidence = 0;
    if (deployment.environment) confidence += 0.25;
    if (deployment.llm_provider) confidence += 0.25;
    if (deployment.domain_name) confidence += 0.25;
    if (deployment.api_key) confidence += 0.25;

    return confidence;
  }

  /**
   * Validate extracted data for consistency and completeness
   */
  validateExtractions(extraction) {
    extraction.validation = {
      warnings: [],
      errors: [],
      isValid: true
    };

    // Validate database configurations
    for (const [dbType, config] of Object.entries(extraction.databases)) {
      if (!config.host) {
        extraction.validation.warnings.push(`Missing host for ${dbType} database`);
      }
      if (!config.database) {
        extraction.validation.warnings.push(`Missing database name for ${dbType}`);
      }
    }

    // Validate authentication
    if (extraction.authentication.provider) {
      if (!extraction.authentication.client_id) {
        extraction.validation.warnings.push('Missing client ID for authentication');
      }
      if (!extraction.authentication.client_secret) {
        extraction.validation.warnings.push('Missing client secret for authentication');
      }
    }

    // Validate deployment
    if (!extraction.deployment.domain_name) {
      extraction.validation.warnings.push('Missing domain name for deployment');
    }
    if (!extraction.deployment.api_key) {
      extraction.validation.warnings.push('Missing LLM API key');
    }

    extraction.validation.isValid = extraction.validation.errors.length === 0;
  }

  /**
   * Initialize extraction patterns for different technologies
   */
  initializePatterns() {
    return {
      postgresql: ['postgresql', 'postgres', 'pg', 'psql'],
      mongodb: ['mongodb', 'mongo', 'nosql'],
      qdrant: ['qdrant', 'vector', 'embedding'],
      google: ['google', 'workspace', 'gmail', 'oauth'],
      okta: ['okta', 'sso'],
      azure: ['azure', 'microsoft', 'ad', 'active directory'],
      openai: ['openai', 'gpt', 'chatgpt'],
      anthropic: ['anthropic', 'claude']
    };
  }

  /**
   * Initialize context keywords for better extraction
   */
  initializeContextKeywords() {
    return {
      database: ['host', 'server', 'endpoint', 'connection', 'uri', 'url'],
      authentication: ['sso', 'login', 'auth', 'identity', 'oauth', 'saml'],
      deployment: ['environment', 'production', 'staging', 'development', 'domain', 'ssl'],
      networking: ['network', 'vpc', 'subnet', 'firewall', 'port', 'mapping']
    };
  }
}

module.exports = ConversationExtractor; 