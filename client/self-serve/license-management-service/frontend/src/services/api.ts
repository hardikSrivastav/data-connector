import axios from 'axios'
import type { Customer, License, LicenseCreate, ValidationRequest, ValidationResponse } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8010'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Health checks
export const healthApi = {
  checkHealth: () => api.get('/health/'),
  checkDbHealth: () => api.get('/health/db'),
}

// Customer API
export const customerApi = {
  getCustomers: (skip = 0, limit = 100) => 
    api.get<Customer[]>('/api/customers/', { params: { skip, limit } }),
  
  getCustomer: (customerId: string) => 
    api.get<Customer>(`/api/customers/${customerId}`),
  
  createCustomer: (customer: Omit<Customer, 'id' | 'created_at' | 'updated_at'>) => 
    api.post<Customer>('/api/customers/', customer),
  
  updateCustomer: (customerId: string, customer: Omit<Customer, 'id' | 'created_at' | 'updated_at'>) => 
    api.put<Customer>(`/api/customers/${customerId}`, customer),
  
  deleteCustomer: (customerId: string) => 
    api.delete(`/api/customers/${customerId}`),
}

// License API
export const licenseApi = {
  getLicenses: (skip = 0, limit = 100, customerId?: string) => 
    api.get<License[]>('/api/licenses/', { 
      params: { skip, limit, customer_id: customerId } 
    }),
  
  getLicense: (licenseId: string) => 
    api.get<License>(`/api/licenses/${licenseId}`),
  
  createLicense: (license: LicenseCreate) => 
    api.post<License>('/api/licenses/', license),
  
  revokeLicense: (licenseId: string, reason: string) => 
    api.put(`/api/licenses/${licenseId}/revoke`, null, { 
      params: { reason } 
    }),
  
  getLicenseToken: (licenseId: string) => 
    api.get<{ license_id: string; license_token: string; expires_at?: string }>
      (`/api/licenses/${licenseId}/token`),
}

// Validation API
export const validationApi = {
  validateLicense: (request: ValidationRequest) => 
    api.post<ValidationResponse>('/api/validation/validate', request),
  
  getPublicKey: () => 
    api.get<{ public_key: string; algorithm: string; key_id: string }>
      ('/api/validation/public-key'),
  
  reportUsage: (data: {
    license_id: string
    event_type: string
    event_data?: Record<string, any>
    user_count?: number
    resource_usage?: Record<string, any>
    client_info?: Record<string, any>
  }) => api.post('/api/validation/usage', data),
  
  getLicenseStatus: (licenseId: string) => 
    api.get(`/api/validation/license/${licenseId}/status`),
}

export default api