import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, FileText, Clock, User, AlertCircle } from 'lucide-react';
import { apiService } from '../services/apiService';
import type { Template, Session } from '../types';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [recentSessions, setRecentSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Test backend connection first
      await apiService.healthCheck();
      
      // Load templates
      const templatesData = await apiService.getTemplates();
      setTemplates(templatesData);
      
    } catch (err) {
      setError(apiService.getErrorMessage(err));
      console.error('Error loading data:', err);
    } finally {
      setLoading(false);
    }
  };

  const createSession = async (templateVersion: string) => {
    try {
      const session = await apiService.createSession({
        user_id: 'demo-user',
        template_version: templateVersion,
        project_context: {}
      });
      
      navigate(`/editor/${session.id}`);
    } catch (err) {
      setError(apiService.getErrorMessage(err));
      console.error('Error creating session:', err);
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
          AI-Powered Template Editor
        </h1>
        <p className="text-xl text-secondary-600 max-w-2xl mx-auto">
          Transform generic authentication templates into production-ready files with intelligent AI guidance
        </p>
      </div>

      {/* Templates Section */}
      <div>
        <h2 className="text-2xl font-bold text-secondary-900 mb-6">
          Available Templates
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
                      {template.version}
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
            <span>Choose a template that matches your authentication needs</span>
          </div>
          <div className="flex items-start space-x-2">
            <span className="font-semibold">2.</span>
            <span>Chat with the AI agent to customize your configuration</span>
          </div>
          <div className="flex items-start space-x-2">
            <span className="font-semibold">3.</span>
            <span>Review and validate your generated files</span>
          </div>
          <div className="flex items-start space-x-2">
            <span className="font-semibold">4.</span>
            <span>Download your production-ready authentication files</span>
          </div>
        </div>
      </div>
    </div>
  );
};