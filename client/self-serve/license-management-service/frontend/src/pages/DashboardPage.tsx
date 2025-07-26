import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { 
  Download, 
  BarChart3, 
  Users, 
  Calendar,
  ExternalLink,
  Plus
} from 'lucide-react'
import { apiClient } from '../services/api'
import { License, UsageAnalytics } from '../types'

export function DashboardPage() {
  const [customerId, setCustomerId] = useState<string | null>(null)

  useEffect(() => {
    const id = sessionStorage.getItem('ceneca_customer_id')
    if (id) {
      setCustomerId(id)
    }
  }, [])

  const { data: dashboardData, isLoading } = useQuery({
    queryKey: ['customer-dashboard', customerId],
    queryFn: () => apiClient.getCustomerDashboard(customerId!),
    enabled: !!customerId,
  })

  const { data: analyticsData } = useQuery({
    queryKey: ['usage-analytics', customerId],
    queryFn: () => apiClient.getUsageAnalytics(customerId!),
    enabled: !!customerId,
  })

  if (!customerId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4 font-baskerville">Customer ID Required</h2>
          <p className="text-gray-600 mb-4 font-baskerville">
            Please provide your customer ID to access the dashboard.
          </p>
          <Link to="/" className="btn btn-primary">
            Go Home
          </Link>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-600 font-baskerville">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  const customer = dashboardData?.customer
  const licenses = dashboardData?.licenses || []
  const activeLicense = licenses.find((l: License) => l.is_active)

  return (
    <div className="min-h-screen">
      {/* Header */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-2xl font-bold text-primary font-baskerville">
                Ceneca License Portal
              </h1>
              <p className="text-gray-600 font-baskerville">
                {customer?.company_name || 'Loading...'}
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500 font-mono">
                ID: {customerId.substring(0, 8)}...
              </span>
              <Link to="/plans" className="btn btn-secondary">
                <Plus className="h-4 w-4 mr-2" />
                New License
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeLicense ? (
          // Has License - Show Dashboard
          <div className="space-y-8">
            {/* Current License Status */}
            <div className="card">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold mb-2 font-baskerville">
                    Active License: {activeLicense.plan.charAt(0).toUpperCase() + activeLicense.plan.slice(1)}
                  </h2>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-4 text-sm text-gray-600">
                      <div className="flex items-center">
                        <Users className="h-4 w-4 mr-2" />
                        <span className="font-baskerville">
                          Up to {activeLicense.max_seats} seats
                        </span>
                      </div>
                      <div className="flex items-center">
                        <BarChart3 className="h-4 w-4 mr-2" />
                        <span className="font-baskerville">
                          {activeLicense.features.length} features
                        </span>
                      </div>
                    </div>
                    {activeLicense.trial_expires_at && (
                      <div className="flex items-center text-sm">
                        <Calendar className="h-4 w-4 mr-2 text-orange-500" />
                        <span className="text-orange-600 font-medium font-baskerville">
                          Trial expires {new Date(activeLicense.trial_expires_at).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-600 mb-1 font-baskerville">Active</div>
                  <div className="text-sm text-gray-500 font-baskerville">
                    Created {new Date(activeLicense.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Download License */}
              <div className="card bg-gradient-to-r from-primary to-purple-600 text-white">
                <h3 className="text-xl font-semibold mb-2 font-baskerville">Download License</h3>
                <p className="text-purple-100 mb-4 font-baskerville">
                  Get your license file and deployment instructions for on-premise setup.
                </p>
                <Link
                  to={`/license/${activeLicense.id}`}
                  className="inline-flex items-center px-4 py-2 bg-white text-primary rounded-lg font-medium hover:bg-gray-50 transition-colors font-baskerville"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download & Deploy
                </Link>
              </div>

              {/* Usage Analytics */}
              <div className="card">
                <h3 className="text-xl font-semibold mb-2 font-baskerville">Usage Analytics</h3>
                <p className="text-gray-600 mb-4 font-baskerville">
                  View detailed usage statistics and billing information.
                </p>
                {analyticsData ? (
                  <div className="space-y-2 mb-4">
                    <div className="flex justify-between text-sm">
                      <span className="font-baskerville">Max seats used:</span>
                      <span className="font-bold font-baskerville">{analyticsData.seat_usage.max_seats_used_ever}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="font-baskerville">Total queries:</span>
                      <span className="font-bold font-baskerville">{analyticsData.feature_usage.total_queries.toLocaleString()}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm mb-4 font-baskerville">No usage data yet</p>
                )}
                <button className="btn btn-secondary w-full">
                  <BarChart3 className="h-4 w-4 mr-2" />
                  View Analytics
                </button>
              </div>
            </div>

            {/* License Details */}
            <div className="card">
              <h3 className="text-lg font-medium mb-4 font-baskerville">License Details</h3>
              
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium mb-3 font-baskerville">Features Included</h4>
                  <ul className="space-y-2 text-sm text-gray-600">
                    {activeLicense.features.map((feature) => (
                      <li key={feature} className="font-baskerville">
                        ✓ {feature.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </li>
                    ))}
                  </ul>
                </div>
                
                <div>
                  <h4 className="font-medium mb-3 font-baskerville">License Information</h4>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-gray-600 font-baskerville">License Key:</dt>
                      <dd className="font-mono text-xs">
                        {activeLicense.license_key}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-600 font-baskerville">Plan:</dt>
                      <dd className="font-baskerville">{activeLicense.plan.charAt(0).toUpperCase() + activeLicense.plan.slice(1)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-600 font-baskerville">Status:</dt>
                      <dd className="text-green-600 font-medium font-baskerville">Active</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-600 font-baskerville">Expires:</dt>
                      <dd className="font-baskerville">{new Date(activeLicense.expires_at).toLocaleDateString()}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ) : (
          // No License - Show Get Started
          <div className="text-center py-16">
            <div className="max-w-md mx-auto">
              <div className="w-24 h-24 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Users className="h-12 w-12 text-primary" />
              </div>
              
              <h2 className="text-2xl font-bold mb-4 font-baskerville">
                Welcome to Ceneca License Portal
              </h2>
              <p className="text-gray-600 mb-8 font-baskerville">
                Get started by selecting a plan and generating your first license for on-premise deployment.
              </p>
              
              <Link to="/plans" className="btn btn-primary">
                Choose Your Plan
                <ExternalLink className="h-5 w-5 ml-2" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}