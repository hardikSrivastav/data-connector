export interface Customer {
  id: string
  company_name: string
  contact_email: string
  industry_classification?: string
  created_at: string
  updated_at?: string
}

export interface License {
  id: string
  customer_id: string
  product_sku: string
  edition_tier: string
  license_type: 'perpetual' | 'subscription' | 'trial'
  start_date: string
  expiration_date?: string
  grace_period_days: number
  user_limit?: number
  node_limit?: number
  feature_flags: Record<string, boolean>
  resource_limits: Record<string, any>
  binding_type: 'strict' | 'flexible' | 'none'
  hardware_signatures: string[]
  tolerance_level: number
  phone_home_frequency: number
  offline_grace_period: number
  usage_reporting_level: string
  issue_date: string
  issuer: string
  sales_order_reference?: string
  support_tier?: string
  is_active: boolean
  revoked_at?: string
  revocation_reason?: string
  license_token?: string
  created_at: string
  updated_at?: string
}

export interface LicenseCreate {
  customer_id: string
  product_sku: string
  edition_tier: string
  license_type: 'perpetual' | 'subscription' | 'trial'
  start_date: string
  expiration_date?: string
  grace_period_days?: number
  user_limit?: number
  node_limit?: number
  feature_flags?: Record<string, boolean>
  resource_limits?: Record<string, any>
  binding_type?: 'strict' | 'flexible' | 'none'
  hardware_signatures?: string[]
  tolerance_level?: number
  phone_home_frequency?: number
  offline_grace_period?: number
  usage_reporting_level?: string
  sales_order_reference?: string
  support_tier?: string
}

export interface ValidationRequest {
  license_token: string
  hardware_fingerprint?: Record<string, string>
  client_info?: Record<string, any>
}

export interface ValidationResponse {
  valid: boolean
  license_id?: string
  reason?: string
  expires_at?: string
  feature_flags?: Record<string, boolean>
  user_limit?: number
  node_limit?: number
  resource_limits?: Record<string, any>
}

export interface UsageEvent {
  id: string
  license_id: string
  event_type: string
  event_data?: Record<string, any>
  user_count?: number
  resource_usage?: Record<string, any>
  client_info?: Record<string, any>
  timestamp: string
}