const TemplateLoader = require('./templateLoader');
const TemplateProcessor = require('./templateProcessor');
const ConversationExtractor = require('./conversationExtractor');

/**
 * Deployment Generator - Orchestrates the entire template-based deployment generation process
 * Follows the architecture outlined in conversational-deployment-configurator.md
 */
class DeploymentGenerator {
  constructor() {
    this.templateLoader = new TemplateLoader();
    this.templateProcessor = new TemplateProcessor();
    this.conversationExtractor = new ConversationExtractor();
    this.isInitialized = false;
  }

  /**
   * Initialize the generator by loading all available templates
   */
  async initialize() {
    if (this.isInitialized) return;

    try {
      console.log('Initializing Deployment Generator...');
      
      // Load all deployment templates
      await this.templateLoader.loadTemplates();
      
      // Validate required templates exist
      await this.templateLoader.validateTemplates();
      
      this.isInitialized = true;
      console.log('Deployment Generator initialized successfully');
      
      // Log available templates and their placeholders
      this.logAvailableTemplates();
      
    } catch (error) {
      console.error('Failed to initialize Deployment Generator:', error);
      throw error;
    }
  }

  /**
   * Generate deployment package from conversation messages
   */
  async generateFromConversation(messages, existingConfig = {}) {
    await this.ensureInitialized();

    try {
      console.log('Starting deployment generation from conversation...');
      
      // Step 1: Extract configuration from conversation
      const extractedConfig = this.conversationExtractor.extractFromConversation(messages, existingConfig);
      console.log('Extracted configuration:', JSON.stringify(extractedConfig, null, 2));

      // Step 2: Validate we have enough information
      this.validateExtractionCompleteness(extractedConfig);

      // Step 3: Generate deployment files
      const deploymentPackage = await this.generateDeploymentPackage(extractedConfig);

      return {
        success: true,
        extractedConfig,
        deploymentPackage,
        metadata: {
          templatesUsed: Object.keys(deploymentPackage.files),
          confidence: extractedConfig.confidence,
          validation: extractedConfig.validation
        }
      };
      
    } catch (error) {
      console.error('Error generating deployment from conversation:', error);
      throw error;
    }
  }

  /**
   * Generate deployment package from extracted configuration
   */
  async generateDeploymentPackage(extractedConfig) {
    await this.ensureInitialized();

    const packageResult = {
      files: {},
      metadata: {
        generatedAt: new Date().toISOString(),
        templateVersions: {},
        substitutions: {},
        unresolved: {}
      }
    };

    // Determine which templates to process based on configuration
    const templatesToProcess = this.selectTemplatesForConfig(extractedConfig);
    console.log('Processing templates:', templatesToProcess);

    // Process each template
    for (const templateName of templatesToProcess) {
      try {
        const template = this.templateLoader.getTemplate(templateName);
        if (!template) {
          console.warn(`Template ${templateName} not found, skipping`);
          continue;
        }

        console.log(`Processing template: ${templateName}`);
        
        // Process the template with extracted configuration
        const processedTemplate = this.templateProcessor.processTemplate(template, extractedConfig);
        
        // Validate the processed template
        this.templateProcessor.validateProcessedTemplate(processedTemplate, template.type);

        // Store the result
        const outputFileName = this.getOutputFileName(templateName, extractedConfig);
        packageResult.files[outputFileName] = processedTemplate.content;
        
        // Store metadata
        packageResult.metadata.substitutions[outputFileName] = processedTemplate.substitutions;
        packageResult.metadata.unresolved[outputFileName] = processedTemplate.unresolved;
        packageResult.metadata.templateVersions[outputFileName] = template.path;

        console.log(`Successfully processed ${templateName} -> ${outputFileName}`);
        
      } catch (error) {
        console.error(`Error processing template ${templateName}:`, error);
        // Continue with other templates, but log the error
        packageResult.metadata.errors = packageResult.metadata.errors || [];
        packageResult.metadata.errors.push({
          template: templateName,
          error: error.message
        });
      }
    }

    // Generate additional helper files
    this.generateHelperFiles(packageResult, extractedConfig);

    console.log(`Generated ${Object.keys(packageResult.files).length} deployment files`);
    return packageResult;
  }

  /**
   * Select which templates to process based on the extracted configuration
   */
  selectTemplatesForConfig(extractedConfig) {
    const templates = [];

    // Always include base configuration
    templates.push('config.yaml');

    // Include authentication config if provider is specified
    if (extractedConfig.authentication?.provider) {
      const authTemplate = this.selectAuthTemplate(extractedConfig.authentication.provider);
      if (authTemplate) {
        templates.push(authTemplate);
      }
    }

    // Include appropriate docker-compose file
    const environment = extractedConfig.deployment?.environment;
    if (environment === 'production') {
      templates.push('enterprise-docker-compose.yml');
      templates.push('enterprise-install.sh');
    } else {
      templates.push('ceneca-docker-compose.yml');
      templates.push('install.sh');
    }

    return templates;
  }

  /**
   * Select the appropriate authentication template
   */
  selectAuthTemplate(provider) {
    const authTemplates = {
      'google': 'auth-config-google.yaml',
      'okta': 'auth-config.yaml.template',
      'azure': 'auth-config-azure.yaml',
      'auth0': 'auth-config-auth0.yaml'
    };

    return authTemplates[provider] || 'auth-config.yaml.template';
  }

  /**
   * Get the output filename for a processed template
   */
  getOutputFileName(templateName, extractedConfig) {
    // Remove .template extension and adjust names
    let fileName = templateName.replace('.template', '');
    
    // Specific filename mappings
    const fileNameMappings = {
      'enterprise-docker-compose.yml': 'docker-compose.yml',
      'ceneca-docker-compose.yml': 'docker-compose.yml',
      'enterprise-install.sh': 'install.sh'
    };

    return fileNameMappings[fileName] || fileName;
  }

  /**
   * Generate additional helper files (README, .env template, etc.)
   */
  generateHelperFiles(packageResult, extractedConfig) {
    // Generate .env file
    packageResult.files['.env'] = this.generateEnvFile(extractedConfig);
    
    // Generate README with deployment instructions
    packageResult.files['README.md'] = this.generateReadme(extractedConfig, packageResult);
    
    // Generate deployment validation script
    packageResult.files['validate-deployment.sh'] = this.generateValidationScript(extractedConfig);
  }

  /**
   * Generate .env file content
   */
  generateEnvFile(extractedConfig) {
    const envContent = [
      '# Ceneca Deployment Environment Variables',
      '# Generated automatically - update as needed',
      '',
      `# LLM Configuration`,
      `LLM_API_KEY=${extractedConfig.deployment?.api_key || 'your_api_key_here'}`,
      '',
      `# Environment`,
      `ENVIRONMENT=${extractedConfig.deployment?.environment || 'development'}`,
      '',
      `# Domain Configuration`,
      `DOMAIN_NAME=${extractedConfig.deployment?.domain_name || 'ceneca.yourcompany.com'}`,
      ''
    ];

    // Add authentication variables if configured
    if (extractedConfig.authentication?.provider) {
      envContent.push('# Authentication Configuration');
      envContent.push(`OIDC_PROVIDER=${extractedConfig.authentication.provider}`);
      
      if (extractedConfig.authentication.client_id) {
        envContent.push(`OIDC_CLIENT_ID=${extractedConfig.authentication.client_id}`);
      }
      
      if (extractedConfig.authentication.client_secret) {
        envContent.push(`OIDC_CLIENT_SECRET=${extractedConfig.authentication.client_secret}`);
      }
      
      if (extractedConfig.authentication.okta_domain) {
        envContent.push(`OIDC_ISSUER=https://${extractedConfig.authentication.okta_domain}/oauth2/default`);
        envContent.push(`OIDC_DISCOVERY_URL=https://${extractedConfig.authentication.okta_domain}/oauth2/default/.well-known/openid-configuration`);
      }
      
      envContent.push('');
    }

    return envContent.join('\n');
  }

  /**
   * Generate README with deployment instructions
   */
  generateReadme(extractedConfig, packageResult) {
    const readme = [
      '# Ceneca Deployment Package',
      '',
      'This deployment package was generated based on your conversation with the Ceneca deployment assistant.',
      '',
      '## Configuration Summary',
      '',
      '### Databases Configured:',
      ...Object.keys(extractedConfig.databases).map(db => {
        const config = extractedConfig.databases[db];
        if (config.use_env_var && config.env_var) {
          return `- ${db.toUpperCase()}: Using environment variable \${${config.env_var}}`;
        } else {
          return `- ${db.toUpperCase()}: ${config.host || 'localhost'}`;
        }
      }),
      '',
      '### Authentication:',
      extractedConfig.authentication?.provider ? 
        `- Provider: ${extractedConfig.authentication.provider.toUpperCase()}` : 
        '- No SSO configured',
      '',
      '### Environment:',
      `- Type: ${extractedConfig.deployment?.environment || 'development'}`,
      `- Domain: ${extractedConfig.deployment?.domain_name || 'not specified'}`,
      `- LLM Provider: ${extractedConfig.deployment?.llm_provider || 'not specified'}`,
      '',
      '## Quick Start',
      '',
      '1. **Review Configuration**: Check all `.yaml` files and update any placeholders',
      '2. **Set Environment Variables**: Update the `.env` file with your actual values',
      '3. **Run Installation**: Execute `./install.sh` to start deployment',
      '4. **Validate Deployment**: Run `./validate-deployment.sh` to check everything is working',
      '',
      '## Files Included',
      '',
      ...Object.keys(packageResult.files).map(file => `- \`${file}\`: ${this.getFileDescription(file)}`),
      '',
      '## Next Steps',
      '',
      '1. Update database credentials in configuration files',
      '2. Configure SSL certificates if needed',
      '3. Set up monitoring and logging',
      '4. Test the deployment in a staging environment first',
      '',
      '## Support',
      '',
      'If you encounter any issues, please check the validation output and logs.',
      'For additional support, contact the Ceneca team.',
      '',
      `Generated on: ${new Date().toISOString()}`,
      ''
    ];

    return readme.join('\n');
  }

  /**
   * Get description for a file in the package
   */
  getFileDescription(fileName) {
    const descriptions = {
      'config.yaml': 'Main Ceneca configuration file',
      'auth-config.yaml': 'Authentication and SSO configuration',
      'docker-compose.yml': 'Docker container orchestration',
      'install.sh': 'Installation script',
      '.env': 'Environment variables',
      'README.md': 'This documentation file',
      'validate-deployment.sh': 'Deployment validation script'
    };

    return descriptions[fileName] || 'Configuration file';
  }

  /**
   * Generate validation script
   */
  generateValidationScript(extractedConfig) {
    const script = [
      '#!/bin/bash',
      '# Ceneca Deployment Validation Script',
      '',
      'echo "Validating Ceneca deployment..."',
      '',
      '# Check if Docker is running',
      'if ! docker info >/dev/null 2>&1; then',
      '    echo "ERROR: Docker is not running"',
      '    exit 1',
      'fi',
      '',
      '# Check if containers are running',
      'if ! docker-compose ps | grep -q "Up"; then',
      '    echo "WARNING: Containers may not be running properly"',
      'fi',
      '',
      '# Test database connections',
      ...this.generateDatabaseValidationSteps(extractedConfig.databases),
      '',
      '# Test web interface',
      'if curl -f http://localhost:8787/health >/dev/null 2>&1; then',
      '    echo "✓ Web interface is accessible"',
      'else',
      '    echo "✗ Web interface is not accessible"',
      'fi',
      '',
      'echo "Validation complete!"'
    ];

    return script.join('\n');
  }

  /**
   * Generate database validation steps
   */
  generateDatabaseValidationSteps(databases) {
    const steps = [];
    
    for (const [dbType, config] of Object.entries(databases)) {
      if (config.host) {
        steps.push(`# Test ${dbType} connection`);
        steps.push(`if nc -z ${config.host} ${config.port || 'default_port'} 2>/dev/null; then`);
        steps.push(`    echo "✓ ${dbType} is reachable at ${config.host}"`);
        steps.push(`else`);
        steps.push(`    echo "✗ ${dbType} is not reachable at ${config.host}"`);
        steps.push(`fi`);
        steps.push('');
      }
    }
    
    return steps;
  }

  /**
   * Validate that we have enough information to generate deployment
   */
  validateExtractionCompleteness(extractedConfig) {
    const missing = [];

    // Check database configuration
    if (Object.keys(extractedConfig.databases).length === 0) {
      missing.push('at least one database configuration');
    } else {
      for (const [dbType, config] of Object.entries(extractedConfig.databases)) {
        if (!config.host) {
          missing.push(`${dbType} database host`);
        }
      }
    }

    // Check deployment essentials
    if (!extractedConfig.deployment?.domain_name) {
      missing.push('domain name');
    }

    if (!extractedConfig.deployment?.llm_provider) {
      missing.push('LLM provider');
    }

    // Authentication is optional but warn if partially configured
    if (extractedConfig.authentication?.provider) {
      if (!extractedConfig.authentication.client_id) {
        missing.push(`${extractedConfig.authentication.provider} client ID`);
      }
    }

    if (missing.length > 0) {
      throw new Error(`Cannot generate deployment: missing ${missing.join(', ')}`);
    }
  }

  /**
   * Get available templates and their requirements
   */
  async getAvailableTemplates() {
    await this.ensureInitialized();
    return this.templateLoader.getRequiredInformation();
  }

  /**
   * Get template analysis for debugging
   */
  async getTemplateAnalysis() {
    await this.ensureInitialized();
    
    const analysis = {
      templates: {},
      placeholders: {},
      requirements: this.templateLoader.getRequiredInformation()
    };

    // Analyze each template
    for (const [name, template] of this.templateLoader.templates) {
      analysis.templates[name] = {
        type: template.type,
        placeholderCount: template.placeholders.length,
        placeholders: template.placeholders
      };
    }

    // Get all unique placeholders
    analysis.placeholders = Object.fromEntries(this.templateLoader.getAllPlaceholders());

    return analysis;
  }

  /**
   * Ensure the generator is initialized
   */
  async ensureInitialized() {
    if (!this.isInitialized) {
      await this.initialize();
    }
  }

  /**
   * Log available templates for debugging
   */
  logAvailableTemplates() {
    console.log('\n=== Available Deployment Templates ===');
    for (const [name, template] of this.templateLoader.templates) {
      console.log(`📄 ${name} (${template.type})`);
      console.log(`   Path: ${template.path}`);
      console.log(`   Placeholders: ${template.placeholders.length}`);
      if (template.placeholders.length > 0) {
        template.placeholders.forEach(p => {
          console.log(`     - ${p.placeholder} (${p.type})`);
        });
      }
      console.log('');
    }
    console.log('=====================================\n');
  }
}

module.exports = DeploymentGenerator; 