import axios from 'axios';
import type {
  Template,
  Session,
  WorkspaceData,
  SessionCreateRequest,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8501';

class ApiService {
  private axiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor for debugging
    this.axiosInstance.interceptors.request.use(
      (config) => {
        console.log('API Request:', config.method?.toUpperCase(), config.url);
        return config;
      },
      (error) => {
        console.error('API Request Error:', error);
        return Promise.reject(error);
      }
    );

    // Add response interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response) => {
        return response;
      },
      (error) => {
        console.error('API Response Error:', error);
        if (error.response?.status === 401) {
          console.warn('Unauthorized access');
        }
        return Promise.reject(error);
      }
    );
  }

  // Health check
  async healthCheck(): Promise<any> {
    const response = await this.axiosInstance.get('/health');
    return response.data;
  }

  // Templates
  async getTemplates(): Promise<Template[]> {
    const response = await this.axiosInstance.get('/api/templates');
    return response.data;
  }

  async getTemplate(version: string): Promise<Template> {
    const response = await this.axiosInstance.get(`/api/templates/${version}`);
    return response.data;
  }

  // Sessions
  async createSession(sessionData: SessionCreateRequest): Promise<Session> {
    const response = await this.axiosInstance.post('/api/sessions', sessionData);
    return response.data;
  }

  async getSession(sessionId: string): Promise<Session> {
    const response = await this.axiosInstance.get(`/api/sessions/${sessionId}`);
    return response.data;
  }

  async getWorkspace(sessionId: string): Promise<WorkspaceData> {
    const response = await this.axiosInstance.get(`/api/sessions/${sessionId}/workspace`);
    return response.data;
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.axiosInstance.delete(`/api/sessions/${sessionId}`);
  }

  // Error handling utility
  getErrorMessage(error: any): string {
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.message) {
      return error.message;
    }
    return 'An unexpected error occurred';
  }
}

export const apiService = new ApiService();