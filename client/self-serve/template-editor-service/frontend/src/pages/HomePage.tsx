import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/apiService';
import type { Template, Session, DeploymentScenario } from '../types';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [scenarios, setScenarios] = useState<DeploymentScenario[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [recentSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'scenarios' | 'templates'>('scenarios');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Test backend connection first
      await apiService.healthCheck();
      
      // Load scenarios and templates
      const [scenariosData, templatesData] = await Promise.all([
        apiService.getScenarios(),
        apiService.getTemplates()
      ]);
      
      setScenarios(scenariosData);
      setTemplates(templatesData);
      
    } catch (err) {
      setError(apiService.getErrorMessage(err));
      console.error('Error loading data:', err);
    } finally {
      setLoading(false);
    }
  };

  const createSession = async (templateVersion?: string, scenarioId?: string) => {
    try {
      const session = await apiService.createSession({
        user_id: 'demo-user',
        template_version: templateVersion,
        scenario_id: scenarioId,
        project_context: {},
        variables: {}  // Could be filled from a form later
      });
      
      navigate(`/editor/${session.id}`);
    } catch (err) {
      setError(apiService.getErrorMessage(err));
      console.error('Error creating session:', err);
    }
  };
  
  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'enterprise': return 'text-blue-600';
      case 'development': return 'text-green-600';
      case 'infrastructure': return 'text-purple-600';
      case 'authentication': return 'text-red-600';
      default: return 'text-primary';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground font-baskerville">Loading templates...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card border-red-200 bg-red-50">
        <div>
          <h2 className="text-lg font-semibold mb-2 font-baskerville text-red-800">Connection Error</h2>
          <p className="mb-4 text-red-600 font-baskerville">{error}</p>
          <button
            onClick={loadData}
            className="btn btn-outline"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-16">
      {/* Hero Section */}
      <div className="text-center space-y-6 py-12">
        <h1 className="text-5xl font-bold font-baskerville gradient-text">
          AI-Powered Deployment Editor
        </h1>
        <p className="text-2xl text-muted-foreground max-w-4xl mx-auto font-baskerville">
          Transform deployment scenarios into production-ready configurations with intelligent AI guidance
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-1 bg-muted p-1 rounded-lg max-w-lg mx-auto">
        <button
          onClick={() => setActiveTab('scenarios')}
          className={`flex-1 px-6 py-3 rounded-md font-medium transition-colors font-baskerville ${
            activeTab === 'scenarios'
              ? 'bg-white text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Deployment Scenarios
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`flex-1 px-6 py-3 rounded-md font-medium transition-colors font-baskerville ${
            activeTab === 'templates'
              ? 'bg-white text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Individual Templates
        </button>
      </div>

      {/* Scenarios Section */}
      {activeTab === 'scenarios' && (
        <div>
          <h2 className="text-3xl font-bold font-baskerville mb-12 text-center">
            Deployment Scenarios
          </h2>
          <div className="grid gap-8 md:grid-cols-2 max-w-6xl mx-auto">
            {scenarios.map((scenario) => (
              <div key={scenario.id} className="card">
                <div className="space-y-6">
                  <div>
                    <h3 className="font-semibold text-xl font-baskerville mb-2">
                      {scenario.name}
                    </h3>
                    <p className="text-muted-foreground capitalize font-baskerville">
                      <span className={getCategoryColor(scenario.category)}>{scenario.category}</span> • {scenario.template_versions.length} templates
                    </p>
                  </div>
                  
                  <p className="text-muted-foreground font-baskerville text-lg leading-relaxed">
                    {scenario.description}
                  </p>
                  
                  <div>
                    <p className="font-medium mb-3 font-baskerville">Includes:</p>
                    <div className="flex flex-wrap gap-2">
                      {scenario.template_versions.map((templateVersion) => {
                        const template = templates.find(t => t.version === templateVersion);
                        return (
                          <span
                            key={templateVersion}
                            className="inline-block px-3 py-1 bg-muted text-muted-foreground text-sm rounded font-baskerville"
                          >
                            {template?.category || templateVersion.split('-')[0]}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between pt-6 border-t border-border">
                    <span className="text-muted-foreground font-baskerville">
                      {new Date(scenario.created_at).toLocaleDateString()}
                    </span>
                    
                    <button
                      onClick={() => createSession(undefined, scenario.id)}
                      className="btn btn-primary"
                    >
                      Start Deployment
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Templates Section */}
      {activeTab === 'templates' && (
        <div>
          <h2 className="text-3xl font-bold font-baskerville mb-12 text-center">
            Individual Templates
          </h2>
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3 max-w-7xl mx-auto">
            {templates.map((template) => (
              <div key={template.version} className="card">
                <div className="space-y-6">
                  <div>
                    <h3 className="font-semibold text-xl font-baskerville mb-2">
                      {template.name}
                    </h3>
                    <p className="text-muted-foreground font-baskerville">
                      {template.category} • {template.format}
                    </p>
                  </div>
                  
                  <p className="text-muted-foreground font-baskerville text-lg leading-relaxed">
                    {template.description}
                  </p>
                  
                  <div className="flex items-center justify-between pt-6 border-t border-border">
                    <span className="text-muted-foreground font-baskerville">
                      {new Date(template.created_at).toLocaleDateString()}
                    </span>
                    
                    <button
                      onClick={() => createSession(template.version)}
                      className="btn btn-primary"
                    >
                      Start Editing
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Sessions Section */}
      {recentSessions.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold font-baskerville mb-8">
            Recent Sessions
          </h2>
          <div className="space-y-4">
            {recentSessions.map((session) => (
              <div key={session.id} className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium font-baskerville">
                      {session.template_version}
                    </h3>
                    <p className="text-sm text-muted-foreground font-baskerville">
                      Status: {session.status}
                    </p>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-muted-foreground font-baskerville">
                      {new Date(session.updated_at).toLocaleDateString()}
                    </span>
                    
                    <button
                      onClick={() => navigate(`/editor/${session.id}`)}
                      className="btn btn-outline"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Getting Started Section */}
      <div className="card border-primary/30 max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold font-baskerville mb-8 gradient-text text-center">
          Getting Started
        </h2>
        <div className="space-y-6 font-baskerville text-lg">
          <div className="flex items-start space-x-4">
            <span className="font-semibold text-primary text-xl">1.</span>
            <span className="leading-relaxed">Choose a deployment scenario that matches your infrastructure needs</span>
          </div>
          <div className="flex items-start space-x-4">
            <span className="font-semibold text-primary text-xl">2.</span>
            <span className="leading-relaxed">Chat with the AI agent to configure all related files at once</span>
          </div>
          <div className="flex items-start space-x-4">
            <span className="font-semibold text-primary text-xl">3.</span>
            <span className="leading-relaxed">Review cross-file dependencies and validate your configuration</span>
          </div>
          <div className="flex items-start space-x-4">
            <span className="font-semibold text-primary text-xl">4.</span>
            <span className="leading-relaxed">Download your complete, production-ready deployment package</span>
          </div>
        </div>
      </div>
    </div>
  );
};