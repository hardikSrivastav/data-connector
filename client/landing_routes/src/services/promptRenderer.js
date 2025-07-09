const nunjucks = require('nunjucks');
const path = require('path');

class PromptRenderer {
  constructor() {
    // Configure nunjucks environment
    this.env = nunjucks.configure(path.join(__dirname, '..', '..', 'prompts'), {
      autoescape: false, // We want raw text output for prompts
      throwOnUndefined: false,
      trimBlocks: true,
      lstripBlocks: true
    });
    
    // Add custom filters if needed
    this.env.addFilter('tojson', function(obj) {
      return JSON.stringify(obj);
    });

    this.env.addFilter('lower', function(str) {
      return str ? str.toLowerCase() : '';
    });
  }

  /**
   * Render the deployment assistant system prompt
   * @param {Object} context - Template context variables
   * @param {Array} context.availableTools - Array of available tools with name and description
   * @param {Object} context.userInfo - User context information
   * @param {string} context.userMessage - Current user message for contextual hints
   * @param {Object} context.contextualRequirements - Discovered requirements organized by category
   * @returns {string} Rendered system prompt
   */
  renderDeploymentAssistant(context) {
    try {
      return this.env.render('deployment-assistant.jinja', context);
    } catch (error) {
      console.error('Error rendering deployment assistant prompt:', error);
      throw new Error(`Failed to render prompt template: ${error.message}`);
    }
  }

  /**
   * Render any template by name with given context
   * @param {string} templateName - Name of the template file
   * @param {Object} context - Template context variables
   * @returns {string} Rendered template
   */
  render(templateName, context) {
    try {
      return this.env.render(templateName, context);
    } catch (error) {
      console.error(`Error rendering template ${templateName}:`, error);
      throw new Error(`Failed to render template ${templateName}: ${error.message}`);
    }
  }

  /**
   * Extract contextual requirements from user message and conversation history
   * @param {string} userMessage - Current user message
   * @param {Array} conversationHistory - Previous conversation messages
   * @returns {Object} Categorized requirements
   */
  extractContextualRequirements(userMessage, conversationHistory = []) {
    const requirements = {
      databases: [],
      authentication: [],
      networking: [],
      scaling: [],
      integrations: []
    };

    // Combine current message with conversation history for analysis
    const allText = [userMessage, ...conversationHistory.map(msg => msg.content)].join(' ').toLowerCase();

    // Technology detection configuration - easily extensible
    const techConfig = {
      databases: {
        'PostgreSQL': ['postgres', 'postgresql', 'pg', 'psql'],
        'MongoDB': ['mongo', 'mongodb', 'nosql'],
        'MySQL': ['mysql'],
        'Redis': ['redis'],
        'SQLite': ['sqlite'],
        'MariaDB': ['mariadb'],
        'CassandraDB': ['cassandra'],
        'InfluxDB': ['influxdb', 'influx'],
        'ElasticSearch': ['elasticsearch', 'elastic'],
        'Qdrant': ['qdrant', 'vector db', 'vector database']
      },
      authentication: {
        'Google OAuth/SSO': ['google oauth', 'google sso', 'google auth'],
        'Azure AD': ['azure ad', 'azure active directory', 'azure sso'],
        'Okta': ['okta'],
        'Auth0': ['auth0'],
        'LDAP': ['ldap', 'active directory'],
        'SAML': ['saml'],
        'JWT': ['jwt', 'json web token'],
        'Basic Auth': ['basic auth', 'username password']
      },
      networking: {
        'SSL/TLS encryption': ['ssl', 'https', 'tls', 'certificate'],
        'Load balancer/reverse proxy': ['load balancer', 'nginx', 'apache', 'reverse proxy'],
        'CDN integration': ['cdn', 'cloudflare', 'cloudfront'],
        'VPN': ['vpn', 'virtual private network'],
        'Firewall': ['firewall', 'security group']
      },
      scaling: {
        'Containerized deployment': ['docker', 'container', 'containerized'],
        'Kubernetes orchestration': ['kubernetes', 'k8s', 'kubectl'],
        'Microservices architecture': ['microservice', 'microservices', 'service mesh'],
        'Auto-scaling': ['auto scale', 'autoscaling', 'scaling'],
        'Load balancing': ['load balancing', 'horizontal scaling']
      },
      integrations: {
        'Shopify': ['shopify', 'shopify api'],
        'Stripe': ['stripe', 'payment processing'],
        'Slack': ['slack', 'slack api'],
        'AWS': ['aws', 'amazon web services'],
        'Google Cloud': ['gcp', 'google cloud'],
        'Azure': ['azure cloud', 'microsoft azure'],
        'GitHub': ['github', 'git integration'],
        'Zendesk': ['zendesk', 'customer support']
      }
    };

    // Dynamically detect technologies based on configuration
    for (const [category, technologies] of Object.entries(techConfig)) {
      for (const [techName, keywords] of Object.entries(technologies)) {
        if (keywords.some(keyword => allText.includes(keyword))) {
          if (!requirements[category].includes(techName)) {
            requirements[category].push(techName);
          }
        }
      }
    }

    // Filter out empty categories
    return Object.fromEntries(
      Object.entries(requirements).filter(([key, value]) => value.length > 0)
    );
  }
}

module.exports = PromptRenderer; 