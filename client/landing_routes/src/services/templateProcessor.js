/**
 * Template Processor - Fills placeholders in actual deployment templates
 * Uses collected conversation data to substitute variables in real template files
 */
class TemplateProcessor {
  constructor() {
    this.substitutionMap = new Map();
  }

  /**
   * Process a template by substituting placeholders with actual values
   */
  processTemplate(template, extractedConfig) {
    if (!template || !template.content) {
      throw new Error('Invalid template provided');
    }

    // Build substitution map from extracted config
    this.buildSubstitutionMap(extractedConfig, template.placeholders);

    // Apply substitutions to template content
    let processedContent = template.content;

    // Process each placeholder
    for (const placeholder of template.placeholders) {
      const value = this.getSubstitutionValue(placeholder, extractedConfig);
      if (value !== null) {
        processedContent = this.substituteValue(processedContent, placeholder, value);
      }
    }

    // Handle conditional sections (commented/uncommented blocks)
    processedContent = this.processConditionalSections(processedContent, extractedConfig);

    return {
      content: processedContent,
      substitutions: Array.from(this.substitutionMap.entries()),
      unresolved: this.findUnresolvedPlaceholders(processedContent)
    };
  }

  /**
   * Build a map of placeholder -> value substitutions
   */
  buildSubstitutionMap(extractedConfig, placeholders) {
    this.substitutionMap.clear();

    // Map database configurations
    if (extractedConfig.databases) {
      if (extractedConfig.databases.postgresql) {
        const pg = extractedConfig.databases.postgresql;
        
        // Handle environment variable vs direct values
        if (pg.use_env_var && pg.env_var) {
          // Use environment variable reference
          this.substitutionMap.set('your-postgres-host', `\${${pg.env_var}}`);
          this.substitutionMap.set('your_database', `\${${pg.env_var}}`);
          this.substitutionMap.set('user:password', `\${${pg.env_var}}`);
        } else {
          // Use direct values
          this.substitutionMap.set('your-postgres-host', pg.host || 'localhost');
          this.substitutionMap.set('your_database', pg.database || 'ceneca');
          this.substitutionMap.set('user:password', `${pg.username || 'ceneca_user'}:${pg.password || 'secure_password'}`);
        }
      }

      if (extractedConfig.databases.mongodb) {
        const mongo = extractedConfig.databases.mongodb;
        this.substitutionMap.set('your-mongodb-host', mongo.host || 'localhost');
        this.substitutionMap.set('your_database', mongo.database || 'ceneca');
      }

      if (extractedConfig.databases.qdrant) {
        const qdrant = extractedConfig.databases.qdrant;
        this.substitutionMap.set('your-qdrant-host', qdrant.host || 'localhost');
        this.substitutionMap.set('your-qdrant-api-key-if-needed', qdrant.api_key || '');
      }
    }

    // Map authentication configurations
    if (extractedConfig.authentication) {
      const auth = extractedConfig.authentication;
      this.substitutionMap.set('OIDC_PROVIDER', auth.provider || 'okta');
      
      // Handle environment variables for sensitive auth data
      if (auth.client_id && typeof auth.client_id === 'object' && auth.client_id.use_env_var) {
        this.substitutionMap.set('OIDC_CLIENT_ID', `\${${auth.client_id.env_var}}`);
      } else {
        this.substitutionMap.set('OIDC_CLIENT_ID', auth.client_id || '');
      }
      
      if (auth.client_secret && typeof auth.client_secret === 'object' && auth.client_secret.use_env_var) {
        this.substitutionMap.set('OIDC_CLIENT_SECRET', `\${${auth.client_secret.env_var}}`);
      } else {
        this.substitutionMap.set('OIDC_CLIENT_SECRET', auth.client_secret || '');
      }
      
      if (auth.provider === 'okta') {
        this.substitutionMap.set('OIDC_ISSUER', `https://${auth.okta_domain}/oauth2/default`);
        this.substitutionMap.set('OIDC_DISCOVERY_URL', `https://${auth.okta_domain}/oauth2/default/.well-known/openid-configuration`);
      }
      
      // Role mappings
      if (auth.role_mappings) {
        this.substitutionMap.set('ROLE_GROUP_1', Object.keys(auth.role_mappings)[0] || 'Data Analysts');
        this.substitutionMap.set('ROLE_VALUE_1', Object.values(auth.role_mappings)[0] || 'analyst');
        this.substitutionMap.set('ROLE_GROUP_2', Object.keys(auth.role_mappings)[1] || 'Admins');
        this.substitutionMap.set('ROLE_VALUE_2', Object.values(auth.role_mappings)[1] || 'admin');
        this.substitutionMap.set('ROLE_GROUP_3', Object.keys(auth.role_mappings)[2] || 'Viewers');
        this.substitutionMap.set('ROLE_VALUE_3', Object.values(auth.role_mappings)[2] || 'viewer');
      }
    }

    // Map deployment configurations
    if (extractedConfig.deployment) {
      const deploy = extractedConfig.deployment;
      this.substitutionMap.set('DOMAIN_NAME', deploy.domain_name || 'ceneca.yourcompany.com');
      
      // Handle API key as environment variable
      if (deploy.api_key && typeof deploy.api_key === 'object' && deploy.api_key.use_env_var) {
        this.substitutionMap.set('LLM_API_KEY', `\${${deploy.api_key.env_var}}`);
      } else {
        this.substitutionMap.set('LLM_API_KEY', deploy.api_key || 'your_api_key_here');
      }
      
      // Set logging level based on environment
      const logLevel = deploy.environment === 'production' ? 'info' : 'debug';
      this.substitutionMap.set('info', logLevel);
    }
  }

  /**
   * Get the substitution value for a specific placeholder
   */
  getSubstitutionValue(placeholder, extractedConfig) {
    // First check direct mapping
    if (this.substitutionMap.has(placeholder.placeholder)) {
      return this.substitutionMap.get(placeholder.placeholder);
    }

    // Check by name
    if (this.substitutionMap.has(placeholder.name)) {
      return this.substitutionMap.get(placeholder.name);
    }

    // Handle specific placeholder types
    switch (placeholder.type) {
      case 'env_var':
        return this.handleEnvVarPlaceholder(placeholder, extractedConfig);
      case 'descriptive':
        return this.handleDescriptivePlaceholder(placeholder, extractedConfig);
      case 'credential':
        return this.handleCredentialPlaceholder(placeholder, extractedConfig);
      case 'api_key':
        return this.handleApiKeyPlaceholder(placeholder, extractedConfig);
      default:
        return null;
    }
  }

  /**
   * Handle environment variable style placeholders
   */
  handleEnvVarPlaceholder(placeholder, extractedConfig) {
    const envName = placeholder.name;
    
    // Check if we have a direct mapping
    if (this.substitutionMap.has(envName)) {
      return this.substitutionMap.get(envName);
    }

    // Handle common environment variables
    switch (envName) {
      case 'LLM_API_KEY':
        return extractedConfig.deployment?.api_key || 'your_api_key_here';
      case 'DOMAIN_NAME':
        return extractedConfig.deployment?.domain_name || 'ceneca.yourcompany.com';
      case 'OIDC_PROVIDER':
        return extractedConfig.authentication?.provider || 'okta';
      default:
        return null;
    }
  }

  /**
   * Handle descriptive placeholders (your-hostname, etc.)
   */
  handleDescriptivePlaceholder(placeholder, extractedConfig) {
    const name = placeholder.name;
    
    if (name.includes('postgres')) {
      return extractedConfig.databases?.postgresql?.host || 'your-postgres-host';
    }
    if (name.includes('mongo')) {
      return extractedConfig.databases?.mongodb?.host || 'your-mongodb-host';
    }
    if (name.includes('qdrant')) {
      return extractedConfig.databases?.qdrant?.host || 'your-qdrant-host';
    }
    if (name.includes('database')) {
      return extractedConfig.databases?.postgresql?.database || 
             extractedConfig.databases?.mongodb?.database || 'ceneca';
    }
    
    return null;
  }

  /**
   * Handle credential placeholders
   */
  handleCredentialPlaceholder(placeholder, extractedConfig) {
    // Look for database credentials
    if (extractedConfig.databases?.postgresql) {
      const pg = extractedConfig.databases.postgresql;
      return `${pg.username || 'ceneca_user'}:${pg.password || 'secure_password'}`;
    }
    
    if (extractedConfig.databases?.mongodb) {
      const mongo = extractedConfig.databases.mongodb;
      return `${mongo.username || 'ceneca_user'}:${mongo.password || 'secure_password'}`;
    }
    
    return 'user:password';
  }

  /**
   * Handle API key placeholders
   */
  handleApiKeyPlaceholder(placeholder, extractedConfig) {
    if (placeholder.name.toLowerCase().includes('qdrant')) {
      return extractedConfig.databases?.qdrant?.api_key || '';
    }
    
    return extractedConfig.deployment?.api_key || 'your_api_key_here';
  }

  /**
   * Substitute a value in the template content
   */
  substituteValue(content, placeholder, value) {
    // Handle different substitution patterns
    if (placeholder.type === 'env_var') {
      // For ${VAR} style placeholders
      return content.replace(new RegExp('\\$\\{' + placeholder.name + '\\}', 'g'), value);
    } else {
      // For direct text replacement
      return content.replace(new RegExp(placeholder.placeholder, 'g'), value);
    }
  }

  /**
   * Process conditional sections based on configuration
   * Uncomments relevant sections based on what's configured
   */
  processConditionalSections(content, extractedConfig) {
    let processedContent = content;

    // Enable auth config if authentication is configured
    if (extractedConfig.authentication?.provider) {
      processedContent = processedContent.replace(
        /# - \.\/auth-config\.yaml/g,
        '- ./auth-config.yaml'
      );
      processedContent = processedContent.replace(
        /# - AUTH_ENABLED=true/g,
        '- AUTH_ENABLED=true'
      );
    }

    // Enable custom networks if specified
    if (extractedConfig.deployment?.custom_networks) {
      for (const network of extractedConfig.deployment.custom_networks) {
        processedContent = processedContent.replace(
          new RegExp(`# - ${network}`, 'g'),
          `- ${network}`
        );
        processedContent = processedContent.replace(
          new RegExp(`# ${network}:`, 'g'),
          `${network}:`
        );
        processedContent = processedContent.replace(
          /#   external: true/g,
          '  external: true'
        );
      }
    }

    // Enable host mappings if specified
    if (extractedConfig.deployment?.host_mappings) {
      processedContent = processedContent.replace(
        /# extra_hosts:/g,
        'extra_hosts:'
      );
      
      // Remove example host mappings
      processedContent = processedContent.replace(
        /#   - "db-postgres\.internal:192\.168\.1\.100"/g,
        ''
      );
      processedContent = processedContent.replace(
        /#   - "db-mongo\.internal:192\.168\.1\.101"/g,
        ''
      );
      processedContent = processedContent.replace(
        /#   - "db-qdrant\.internal:192\.168\.1\.102"/g,
        ''
      );
      
      // Add actual host mappings
      let hostMappings = '';
      for (const [hostname, ip] of Object.entries(extractedConfig.deployment.host_mappings)) {
        hostMappings += `      - "${hostname}:${ip}"\n`;
      }
      
      if (hostMappings) {
        processedContent = processedContent.replace(
          /extra_hosts:\n/,
          `extra_hosts:\n${hostMappings}`
        );
      }
    }

    return processedContent;
  }

  /**
   * Find any unresolved placeholders in the processed content
   */
  findUnresolvedPlaceholders(content) {
    const unresolved = [];
    
    // Find remaining ${VAR} patterns
    const envVarPattern = /\$\{([^}]+)\}/g;
    let match;
    while ((match = envVarPattern.exec(content)) !== null) {
      unresolved.push({
        type: 'env_var',
        placeholder: match[0],
        name: match[1]
      });
    }
    
    // Find remaining descriptive placeholders
    const descriptivePattern = /(your-[a-zA-Z0-9-]+|company-[a-zA-Z0-9-]+)/g;
    while ((match = descriptivePattern.exec(content)) !== null) {
      unresolved.push({
        type: 'descriptive',
        placeholder: match[0],
        name: match[1]
      });
    }
    
    return unresolved;
  }

  /**
   * Validate that critical placeholders have been resolved
   */
  validateProcessedTemplate(processedTemplate, templateType) {
    const unresolved = processedTemplate.unresolved;
    const critical = [];
    
    for (const placeholder of unresolved) {
      if (this.isCriticalPlaceholder(placeholder, templateType)) {
        critical.push(placeholder);
      }
    }
    
    if (critical.length > 0) {
      throw new Error(`Critical placeholders not resolved: ${critical.map(p => p.placeholder).join(', ')}`);
    }
    
    return true;
  }

  /**
   * Determine if a placeholder is critical for the template type
   */
  isCriticalPlaceholder(placeholder, templateType) {
    const criticalPatterns = {
      'main_config': ['host', 'database', 'api_key'],
      'auth_config': ['CLIENT_ID', 'CLIENT_SECRET', 'DOMAIN'],
      'docker_compose': ['LLM_API_KEY'],
      'install_script': []
    };
    
    const critical = criticalPatterns[templateType] || [];
    
    return critical.some(pattern => 
      placeholder.placeholder.toLowerCase().includes(pattern.toLowerCase())
    );
  }
}

module.exports = TemplateProcessor; 