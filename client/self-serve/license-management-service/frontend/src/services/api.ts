const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8020'

// API client with error handling
class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }))
      throw new Error(errorData.message || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Customer endpoints
  async createCustomer(data: { company_name: string; contact_email: string; industry?: string }) {
    return this.request('/api/customers/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getCustomer(customerId: string) {
    return this.request(`/api/customers/${customerId}`)
  }

  async getCustomerDashboard(customerId: string) {
    return this.request(`/api/customers/${customerId}/dashboard`)
  }

  // License endpoints
  async createLicense(data: { customer_id: string; plan: string; trial_days?: number }) {
    return this.request('/api/licenses/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getLicenses(customerId?: string) {
    const params = customerId ? `?customer_id=${customerId}` : ''
    return this.request(`/api/licenses/${params}`)
  }

  async getLicense(licenseId: string) {
    return this.request(`/api/licenses/${licenseId}`)
  }

  async downloadLicense(licenseId: string) {
    return this.request(`/api/licenses/${licenseId}/download`)
  }

  async validateLicense(data: { license_key: string; user_id: string; deployment_id?: string }) {
    return this.request('/api/licenses/validate', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Telemetry endpoints
  async getTelemetryReports(params: { 
    customer_id?: string; 
    license_key?: string; 
    days?: number;
    skip?: number;
    limit?: number;
  } = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, value.toString())
      }
    })
    
    const query = searchParams.toString()
    return this.request(`/api/telemetry/${query ? `?${query}` : ''}`)
  }

  async getUsageAnalytics(customerId: string, days: number = 30) {
    return this.request(`/api/telemetry/analytics/${customerId}?days=${days}`)
  }

  async getBillingData(customerId: string, month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request(`/api/telemetry/billing/${customerId}${params}`)
  }

  // Health check
  async healthCheck() {
    return this.request('/health/')
  }
}

export const apiClient = new ApiClient(API_BASE_URL)