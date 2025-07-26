export interface Customer {
  id: string
  company_name: string
  contact_email: string
  industry?: string
  created_at: string
  updated_at?: string
}

export interface License {
  id: string
  customer_id: string
  license_key: string
  plan: string
  max_seats: number
  features: string[]
  monthly_price?: number
  issued_at: string
  expires_at: string
  trial_expires_at?: string
  jwt_token: string
  is_active: boolean
  created_at: string
}

export interface TelemetryReport {
  id: string
  customer_id: string
  license_id: string
  license_key: string
  report_date: string
  deployment_id?: string
  active_users: {
    unique_daily: number
    peak_concurrent: number
    user_list?: string[]
  }
  usage_stats: {
    queries_executed?: number
    databases_connected?: number
    api_calls?: number
    features_used?: string[]
  }
  system_info: {
    version?: string
    os?: string
    deployment_id?: string
  }
  max_seats_used: number
  overage_seats: number
  created_at: string
}

export interface Plan {
  name: string
  display_name: string
  max_seats: number
  monthly_price: number
  features: string[]
  description: string
  popular?: boolean
}

export interface UsageAnalytics {
  customer_id: string
  period_days: number
  total_reports: number
  unique_deployments: number
  seat_usage: {
    max_seats_used_ever: number
    avg_seats_used: number
    recent_avg_seats: number
    overage_incidents: number
    max_overage: number
  }
  feature_usage: {
    total_queries: number
    total_api_calls: number
    avg_queries_per_day: number
  }
  billing_summary: {
    billable_seats: number
    overage_charges_applicable: boolean
    max_overage_seats: number
  }
}