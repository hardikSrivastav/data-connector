import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, FileText, Clock, User, AlertCircle, Layers, Database, Shield, Server } from 'lucide-react';
import { apiService } from '../services/apiService';
import type { Template, Session, DeploymentScenario } from '../types';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [scenarios, setScenarios] = useState<DeploymentScenario[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [recentSessions, setRecentSessions] = useState<Session[]>([]);
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
  
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'enterprise': return <Server className="w-6 h-6" />;
      case 'development': return <FileText className="w-6 h-6" />;
      case 'infrastructure': return <Database className="w-6 h-6" />;
      case 'authentication': return <Shield className="w-6 h-6" />;
      default: return <Layers className="w-6 h-6" />;
    }
  };
  
  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'enterprise': return 'text-blue-600';
      case 'development': return 'text-green-600';
      case 'infrastructure': return 'text-purple-600';
      case 'authentication': return 'text-red-600';
      default: return 'text-primary-600';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-secondary-600">Loading templates...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card bg-red-50 border-red-200">
        <div className="flex items-center space-x-2 text-red-800">
          <AlertCircle className="w-5 h-5" />
          <div>
            <h2 className="text-lg font-semibold mb-2">Connection Error</h2>
            <p className="mb-4">{error}</p>
            <button
              onClick={loadData}
              className="btn btn-outline"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center">
        <h1 className="text-4xl font-bold text-secondary-900 mb-4">
          AI-Powered Deployment Editor
        </h1>
        <p className="text-xl text-secondary-600 max-w-2xl mx-auto">
          Transform deployment scenarios into production-ready configurations with intelligent AI guidance
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-1 bg-secondary-100 p-1 rounded-lg max-w-md mx-auto mb-8">
        <button
          onClick={() => setActiveTab('scenarios')}
          className={`flex-1 px-4 py-2 rounded-md font-medium transition-colors ${
            activeTab === 'scenarios'
              ? 'bg-white text-primary-600 shadow-sm'
              : 'text-secondary-600 hover:text-secondary-900'
          }`}
        >
          Deployment Scenarios
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`flex-1 px-4 py-2 rounded-md font-medium transition-colors ${
            activeTab === 'templates'
              ? 'bg-white text-primary-600 shadow-sm'
              : 'text-secondary-600 hover:text-secondary-900'
          }`}
        >
          Individual Templates
        </button>
      </div>

      {/* Scenarios Section */}
      {activeTab === 'scenarios' && (
        <div>
          <h2 className="text-2xl font-bold text-secondary-900 mb-6">
            Deployment Scenarios
          </h2>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2">
            {scenarios.map((scenario) => (
              <div key={scenario.id} className="card hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className={getCategoryColor(scenario.category)}>
                      {getCategoryIcon(scenario.category)}
                    </div>
                    <div>
                      <h3 className="font-semibold text-secondary-900">
                        {scenario.name}
                      </h3>
                      <p className="text-sm text-secondary-600 capitalize">
                        {scenario.category} • {scenario.template_versions.length} templates
                      </p>
                    </div>
                  </div>
                </div>
                
                <p className="text-secondary-700 mb-4">
                  {scenario.description}
                </p>
                
                <div className="mb-4">
                  <p className="text-sm font-medium text-secondary-900 mb-2">Includes:</p>
                  <div className="flex flex-wrap gap-1">
                    {scenario.template_versions.map((templateVersion) => {
                      const template = templates.find(t => t.version === templateVersion);
                      return (
                        <span
                          key={templateVersion}
                          className="inline-block px-2 py-1 bg-secondary-100 text-secondary-700 text-xs rounded"
                        >
                          {template?.category || templateVersion.split('-')[0]}
                        </span>
                      );
                    })}
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-sm text-secondary-600">
                    <Clock className="w-4 h-4" />
                    <span>{new Date(scenario.created_at).toLocaleDateString()}</span>
                  </div>
                  
                  <button
                    onClick={() => createSession(undefined, scenario.id)}
                    className="btn btn-primary flex items-center space-x-2"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Start Deployment</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Templates Section */}
      {activeTab === 'templates' && (
        <div>
          <h2 className="text-2xl font-bold text-secondary-900 mb-6">
            Individual Templates
          </h2>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
              <div key={template.version} className="card hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <FileText className="w-6 h-6 text-primary-600" />
                    <div>
                      <h3 className="font-semibold text-secondary-900">
                        {template.name}
                      </h3>
                      <p className="text-sm text-secondary-600">
                        {template.category} • {template.format}
                      </p>
                    </div>
                  </div>
                </div>
                
                <p className="text-secondary-700 mb-4">
                  {template.description}
                </p>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-sm text-secondary-600">
                    <Clock className="w-4 h-4" />
                    <span>{new Date(template.created_at).toLocaleDateString()}</span>
                  </div>
                  
                  <button
                    onClick={() => createSession(template.version)}
                    className="btn btn-primary flex items-center space-x-2"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Start Editing</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Sessions Section */}
      {recentSessions.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold text-secondary-900 mb-6">
            Recent Sessions
          </h2>
          <div className="space-y-4">
            {recentSessions.map((session) => (
              <div key={session.id} className="card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <User className="w-5 h-5 text-secondary-600" />
                    <div>
                      <h3 className="font-medium text-secondary-900">
                        {session.template_version}
                      </h3>
                      <p className="text-sm text-secondary-600">
                        Status: {session.status}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <div className="text-sm text-secondary-600">
                      <Clock className="w-4 h-4 inline mr-1" />
                      {new Date(session.updated_at).toLocaleDateString()}
                    </div>
                    
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
      <div className="card bg-primary-50 border-primary-200">
        <h2 className="text-xl font-bold text-primary-900 mb-4">
          Getting Started
        </h2>
        <div className="space-y-3 text-primary-800">
          <div className="flex items-start space-x-2">
            <span className="font-semibold">1.</span>
            <span>Choose a deployment scenario that matches your infrastructure needs</span>
          </div>
          <div className="flex items-start space-x-2">
            <span className="font-semibold">2.</span>
            <span>Chat with the AI agent to configure all related files at once</span>
          </div>
          <div className="flex items-start space-x-2">
            <span className="font-semibold">3.</span>
            <span>Review cross-file dependencies and validate your configuration</span>
          </div>
          <div className="flex items-start space-x-2">
            <span className="font-semibold">4.</span>
            <span>Download your complete, production-ready deployment package</span>
          </div>
        </div>
      </div>
    </div>
  );
};