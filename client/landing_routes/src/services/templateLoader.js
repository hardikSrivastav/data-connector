const fs = require('fs').promises;
const path = require('path');

/**
 * Template Loader - Reads actual deployment files and identifies placeholders
 * This follows the template-based approach outlined in conversational-deployment-configurator.md
 */
class TemplateLoader {
  constructor() {
    // Path to deploy templates within the backend container
    this.deployPath = '/app/src/deploy-reference';
    this.templates = new Map();
    this.placeholders = new Map();
  }

  /**
   * Load all available deployment templates from the deploy directory
   */
  async loadTemplates() {
    try {
      console.log(`Looking for deploy templates at: ${this.deployPath}`);
      
      const files = await this.scanDeployDirectory();
      
      for (const file of files) {
        const content = await fs.readFile(file.path, 'utf8');
        const placeholders = this.extractPlaceholders(content);
        
        this.templates.set(file.name, {
          path: file.path,
          content: content,
          placeholders: placeholders,
          type: this.determineTemplateType(file.name)
        });
        
        // Store placeholders for analysis
        this.placeholders.set(file.name, placeholders);
      }
      
      console.log(`Loaded ${this.templates.size} deployment templates`);
      return this.templates;
    } catch (error) {
      console.error('Error loading templates:', error);
      throw error;
    }
  }





  /**
   * Scan the deploy directory for template files
   */
  async scanDeployDirectory() {
    const files = [];
    
    // Define template files to scan
    const templateFiles = [
      'config.yaml',
      'auth-config.yaml.template',
      'auth-config-google.yaml',
      'auth-config-azure.yaml',
      'auth-config-auth0.yaml',
      'enterprise-docker-compose.yml',
      'ceneca-docker-compose.yml',
      'install.sh',
      'enterprise-install.sh'
    ];
    
    for (const fileName of templateFiles) {
      const filePath = path.join(this.deployPath, fileName);
      try {
        await fs.access(filePath);
        files.push({
          name: fileName,
          path: filePath
        });
      } catch (error) {
        console.warn(`Template file not found: ${fileName}`);
      }
    }
    
    // Also scan nginx directory
    try {
      const nginxPath = path.join(this.deployPath, 'nginx');
      const nginxFiles = await fs.readdir(nginxPath);
      for (const file of nginxFiles) {
        if (file.endsWith('.conf') || file.endsWith('.template')) {
          files.push({
            name: `nginx/${file}`,
            path: path.join(nginxPath, file)
          });
        }
      }
    } catch (error) {
      console.warn('Nginx templates not found');
    }
    
    return files;
  }

  /**
   * Extract all placeholders from template content
   * Supports multiple placeholder patterns:
   * - ${VARIABLE_NAME} (environment style)
   * - your-hostname (descriptive placeholders)
   * - user:password (credential placeholders)
   */
  extractPlaceholders(content) {
    const placeholders = new Set();
    
    // Pattern 1: ${VARIABLE_NAME} style
    const envVarPattern = /\$\{([^}]+)\}/g;
    let match;
    while ((match = envVarPattern.exec(content)) !== null) {
      placeholders.add({
        type: 'env_var',
        name: match[1],
        placeholder: match[0],
        example: match[1].toLowerCase().replace(/_/g, '-')
      });
    }
    
    // Pattern 2: Descriptive placeholders (your-*, company-*, etc.)
    const descriptivePattern = /(your-[a-zA-Z0-9-]+|company-[a-zA-Z0-9-]+|example\.[a-zA-Z0-9.-]+)/g;
    while ((match = descriptivePattern.exec(content)) !== null) {
      placeholders.add({
        type: 'descriptive',
        name: match[1],
        placeholder: match[0],
        category: this.categorizeDescriptivePlaceholder(match[1])
      });
    }
    
    // Pattern 3: Generic credential patterns
    const credentialPattern = /(user:password|username:password)/g;
    while ((match = credentialPattern.exec(content)) !== null) {
      placeholders.add({
        type: 'credential',
        name: 'auth_credentials',
        placeholder: match[0],
        category: 'authentication'
      });
    }
    
    // Pattern 4: API key patterns
    const apiKeyPattern = /(your[_-]?[a-zA-Z]*[_-]?api[_-]?key[_-]?[a-zA-Z]*)/gi;
    while ((match = apiKeyPattern.exec(content)) !== null) {
      placeholders.add({
        type: 'api_key',
        name: 'api_key',
        placeholder: match[0],
        category: 'authentication'
      });
    }
    
    return Array.from(placeholders);
  }

  /**
   * Categorize descriptive placeholders for better mapping
   */
  categorizeDescriptivePlaceholder(placeholder) {
    if (placeholder.includes('host') || placeholder.includes('server')) {
      return 'database_host';
    }
    if (placeholder.includes('domain') || placeholder.includes('url')) {
      return 'domain';
    }
    if (placeholder.includes('postgres') || placeholder.includes('pg')) {
      return 'postgresql';
    }
    if (placeholder.includes('mongo')) {
      return 'mongodb';
    }
    if (placeholder.includes('qdrant') || placeholder.includes('vector')) {
      return 'qdrant';
    }
    if (placeholder.includes('database') || placeholder.includes('db')) {
      return 'database';
    }
    return 'general';
  }

  /**
   * Determine template type for processing logic
   */
  determineTemplateType(fileName) {
    if (fileName.includes('config.yaml')) return 'main_config';
    if (fileName.includes('auth-config')) return 'auth_config';
    if (fileName.includes('docker-compose')) return 'docker_compose';
    if (fileName.includes('install.sh')) return 'install_script';
    if (fileName.includes('nginx')) return 'nginx_config';
    return 'unknown';
  }

  /**
   * Get template by name
   */
  getTemplate(name) {
    return this.templates.get(name);
  }

  /**
   * Get all placeholders across all templates
   */
  getAllPlaceholders() {
    const allPlaceholders = new Map();
    
    for (const [templateName, placeholders] of this.placeholders) {
      for (const placeholder of placeholders) {
        const key = `${placeholder.category || 'general'}_${placeholder.name}`;
        if (!allPlaceholders.has(key)) {
          allPlaceholders.set(key, {
            ...placeholder,
            usedInTemplates: [templateName]
          });
        } else {
          allPlaceholders.get(key).usedInTemplates.push(templateName);
        }
      }
    }
    
    return allPlaceholders;
  }

  /**
   * Get required information based on loaded templates
   */
  getRequiredInformation() {
    const requirements = {
      databases: new Set(),
      authentication: new Set(),
      deployment: new Set(),
      networking: new Set()
    };
    
    for (const [templateName, template] of this.templates) {
      for (const placeholder of template.placeholders) {
        switch (placeholder.category) {
          case 'postgresql':
          case 'mongodb':
          case 'qdrant':
          case 'database_host':
            requirements.databases.add(placeholder.category);
            break;
          case 'authentication':
            requirements.authentication.add(placeholder.name);
            break;
          case 'domain':
            requirements.deployment.add('domain_configuration');
            break;
          default:
            requirements.deployment.add(placeholder.category || 'general');
        }
      }
    }
    
    // Convert Sets to Arrays for JSON serialization
    return {
      databases: Array.from(requirements.databases),
      authentication: Array.from(requirements.authentication),
      deployment: Array.from(requirements.deployment),
      networking: Array.from(requirements.networking)
    };
  }

  /**
   * Validate that required templates exist
   */
  async validateTemplates() {
    const required = ['config.yaml', 'enterprise-docker-compose.yml'];
    const missing = [];
    
    for (const req of required) {
      if (!this.templates.has(req)) {
        missing.push(req);
      }
    }
    
    if (missing.length > 0) {
      throw new Error(`Missing required templates: ${missing.join(', ')}`);
    }
    
    return true;
  }
}

module.exports = TemplateLoader; 