import json
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

class ScenarioManager:
    def __init__(self):
        self.scenarios = self._create_default_scenarios()
    
    def _create_default_scenarios(self) -> List[Dict]:
        """Create predefined deployment scenarios"""
        scenarios = [
            {
                "id": "basic-ceneca-deployment",
                "name": "Basic Ceneca Deployment",
                "description": "Simple development deployment with application configuration and basic Docker setup",
                "category": "development",
                "template_versions": [
                    "ceneca-config-v1.0.0",
                    "ceneca-deployment-v1.0.0"
                ],
                "dependencies": {
                    "cross_file_variables": {
                        "POSTGRES_HOST": ["ceneca-config-v1.0.0", "ceneca-deployment-v1.0.0"],
                        "MONGODB_HOST": ["ceneca-config-v1.0.0", "ceneca-deployment-v1.0.0"],
                        "LLM_API_KEY_VALUE": ["ceneca-deployment-v1.0.0"]
                    },
                    "validation_rules": [
                        {
                            "rule": "postgres_host_consistency",
                            "description": "PostgreSQL host must match between config.yaml and docker-compose.yml",
                            "files": ["config.yaml.template", "docker-compose.yml.template"],
                            "variables": ["POSTGRES_HOST"]
                        }
                    ]
                },
                "variable_mappings": {
                    "shared_variables": [
                        "POSTGRES_HOST", "POSTGRES_HOST_IP", 
                        "MONGODB_HOST", "MONGODB_HOST_IP",
                        "LLM_API_KEY_VALUE"
                    ]
                }
            },
            {
                "id": "enterprise-oidc-deployment", 
                "name": "Enterprise OIDC Deployment",
                "description": "Complete enterprise deployment with OIDC authentication, NGINX reverse proxy, and SSL",
                "category": "enterprise",
                "template_versions": [
                    "ceneca-config-v1.0.0",
                    "oidc-auth-v1.0.0", 
                    "enterprise-deployment-v1.0.0",
                    "nginx-proxy-v1.0.0"
                ],
                "dependencies": {
                    "cross_file_variables": {
                        "DOMAIN_NAME": ["oidc-auth-v1.0.0", "nginx-proxy-v1.0.0"],
                        "POSTGRES_HOST": ["ceneca-config-v1.0.0", "enterprise-deployment-v1.0.0"],
                        "MONGODB_HOST": ["ceneca-config-v1.0.0", "enterprise-deployment-v1.0.0"],
                        "QDRANT_HOST": ["ceneca-config-v1.0.0", "enterprise-deployment-v1.0.0"],
                        "LLM_API_KEY_VALUE": ["enterprise-deployment-v1.0.0"]
                    },
                    "validation_rules": [
                        {
                            "rule": "domain_consistency",
                            "description": "Domain name must match between auth config and NGINX config",
                            "files": ["auth-config.yaml.template", "nginx.conf.template"],
                            "variables": ["DOMAIN_NAME"]
                        },
                        {
                            "rule": "oidc_callback_url",
                            "description": "OIDC redirect URI must match NGINX domain configuration",
                            "files": ["auth-config.yaml.template", "nginx.conf.template"],
                            "validation": "redirect_uri_format"
                        },
                        {
                            "rule": "database_consistency",
                            "description": "Database hostnames must be consistent across config and deployment",
                            "files": ["config.yaml.template", "docker-compose.yml.template"],
                            "variables": ["POSTGRES_HOST", "MONGODB_HOST", "QDRANT_HOST"]
                        }
                    ]
                },
                "variable_mappings": {
                    "shared_variables": [
                        "DOMAIN_NAME", "LLM_API_KEY_VALUE",
                        "POSTGRES_HOST", "POSTGRES_HOST_IP", "POSTGRES_USERNAME", "POSTGRES_PASSWORD", "POSTGRES_DATABASE",
                        "MONGODB_HOST", "MONGODB_HOST_IP", "MONGODB_USERNAME", "MONGODB_PASSWORD", "MONGODB_DATABASE", 
                        "QDRANT_HOST", "QDRANT_HOST_IP", "QDRANT_API_KEY",
                        "OIDC_PROVIDER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_ISSUER", "OIDC_DISCOVERY_URL"
                    ],
                    "role_mappings": [
                        "ROLE_GROUP_1", "ROLE_VALUE_1",
                        "ROLE_GROUP_2", "ROLE_VALUE_2", 
                        "ROLE_GROUP_3", "ROLE_VALUE_3"
                    ]
                }
            },
            {
                "id": "infrastructure-only",
                "name": "Infrastructure Configuration", 
                "description": "NGINX reverse proxy setup with SSL configuration for existing applications",
                "category": "infrastructure",
                "template_versions": [
                    "nginx-proxy-v1.0.0"
                ],
                "dependencies": {
                    "cross_file_variables": {
                        "DOMAIN_NAME": ["nginx-proxy-v1.0.0"]
                    },
                    "validation_rules": [
                        {
                            "rule": "ssl_certificate_paths",
                            "description": "SSL certificate paths must be valid",
                            "files": ["nginx.conf.template"],
                            "validation": "ssl_path_validation"
                        }
                    ]
                },
                "variable_mappings": {
                    "shared_variables": ["DOMAIN_NAME"]
                }
            },
            {
                "id": "auth-config-only",
                "name": "Authentication Configuration",
                "description": "OIDC/SSO authentication setup for integration with existing infrastructure", 
                "category": "authentication",
                "template_versions": [
                    "oidc-auth-v1.0.0"
                ],
                "dependencies": {
                    "cross_file_variables": {
                        "DOMAIN_NAME": ["oidc-auth-v1.0.0"],
                        "OIDC_PROVIDER": ["oidc-auth-v1.0.0"],
                        "OIDC_CLIENT_ID": ["oidc-auth-v1.0.0"],
                        "OIDC_CLIENT_SECRET": ["oidc-auth-v1.0.0"]
                    },
                    "validation_rules": [
                        {
                            "rule": "oidc_configuration_complete",
                            "description": "All required OIDC parameters must be provided",
                            "files": ["auth-config.yaml.template"],
                            "variables": ["OIDC_PROVIDER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "DOMAIN_NAME"]
                        }
                    ]
                },
                "variable_mappings": {
                    "shared_variables": [
                        "DOMAIN_NAME", "OIDC_PROVIDER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", 
                        "OIDC_ISSUER", "OIDC_DISCOVERY_URL"
                    ],
                    "role_mappings": [
                        "ROLE_GROUP_1", "ROLE_VALUE_1",
                        "ROLE_GROUP_2", "ROLE_VALUE_2",
                        "ROLE_GROUP_3", "ROLE_VALUE_3"
                    ]
                }
            }
        ]
        
        # Add created_at timestamps
        for scenario in scenarios:
            scenario["created_at"] = datetime.utcnow().isoformat()
            
        return scenarios
    
    def get_scenarios(self) -> List[Dict]:
        """Get all available deployment scenarios"""
        return self.scenarios
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[Dict]:
        """Get a specific deployment scenario by ID"""
        for scenario in self.scenarios:
            if scenario["id"] == scenario_id:
                return scenario
        return None
    
    def get_scenarios_by_category(self, category: str) -> List[Dict]:
        """Get deployment scenarios filtered by category"""
        return [s for s in self.scenarios if s["category"] == category]
    
    def get_scenario_categories(self) -> List[str]:
        """Get list of all scenario categories"""
        categories = set(scenario["category"] for scenario in self.scenarios)
        return sorted(list(categories))
    
    def validate_scenario_dependencies(self, scenario_id: str, variables: Dict[str, str]) -> Dict:
        """Validate that variables satisfy scenario dependencies"""
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario:
            return {"valid": False, "errors": [f"Scenario {scenario_id} not found"]}
        
        errors = []
        warnings = []
        
        # Check required shared variables
        shared_vars = scenario.get("variable_mappings", {}).get("shared_variables", [])
        for var in shared_vars:
            if var not in variables or not variables[var]:
                errors.append(f"Required variable '{var}' is missing or empty")
        
        # Check cross-file variable consistency (simplified validation)
        cross_file_vars = scenario.get("dependencies", {}).get("cross_file_variables", {})
        for var_name, template_versions in cross_file_vars.items():
            if var_name in variables and len(template_versions) > 1:
                # This variable is used across multiple templates - consistency is important
                if not variables[var_name]:
                    warnings.append(f"Variable '{var_name}' is used across multiple files but is empty")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def get_scenario_variable_schema(self, scenario_id: str) -> Optional[Dict]:
        """Get combined variable schema for all templates in a scenario"""
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario:
            return None
            
        # This would normally combine schemas from all templates in the scenario
        # For now, return a simplified schema based on variable mappings
        shared_vars = scenario.get("variable_mappings", {}).get("shared_variables", [])
        role_mappings = scenario.get("variable_mappings", {}).get("role_mappings", [])
        
        properties = {}
        required = []
        
        # Add shared variables as required
        for var in shared_vars:
            properties[var] = {
                "type": "string",
                "description": f"Shared variable used across multiple templates in this scenario"
            }
            required.append(var)
        
        # Add role mappings as optional
        for var in role_mappings:
            properties[var] = {
                "type": "string", 
                "description": f"Role mapping variable for OIDC group assignments"
            }
        
        return {
            "type": "object",
            "required": required,
            "properties": properties
        }