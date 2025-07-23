import { useQuery } from '@tanstack/react-query'
import { 
  ArrowRight,
  Calendar,
  Database,
  Zap,
  Settings,
  ExternalLink
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { licenseApi } from '../../services/api'

export default function SimpleDashboard() {
  // Mock customer ID - in real app this would come from auth
  const customerId = "4891c1ae-df14-4959-9d05-49015c7621da"

  const { data: licensesData } = useQuery({
    queryKey: ['customer-licenses', customerId],
    queryFn: () => licenseApi.getLicenses(0, 100, customerId),
  })

  const licenses = licensesData?.data || []
  const currentLicense = licenses[0] // Most recent license

  const getTierDisplayName = (tier: string) => {
    return tier.charAt(0).toUpperCase() + tier.slice(1)
  }

  const getDaysRemaining = (trialExpires: string) => {
    if (!trialExpires) return null
    const expires = new Date(trialExpires)
    const now = new Date()
    const diffTime = expires.getTime() - now.getTime()
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    return Math.max(0, diffDays)
  }

  const handleGoToTemplateEditor = () => {
    if (currentLicense?.license_token) {
      window.location.href = `http://localhost:8500?license=${currentLicense.license_token}`
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Ceneca License Portal</h1>
              <p className="text-gray-600">Test Company</p>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">
                Customer ID: {customerId.substring(0, 8)}...
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentLicense ? (
          // Has License - Show Dashboard
          <div className="space-y-8">
            {/* Current License Status */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-2">
                    Current License: {getTierDisplayName(currentLicense.tier)}
                  </h2>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-4 text-sm text-gray-600">
                      <div className="flex items-center">
                        <Database className="h-4 w-4 mr-2" />
                        {currentLicense.database_limit ? 
                          `${currentLicense.database_limit} databases` : 
                          'Unlimited databases'
                        }
                      </div>
                      <div className="flex items-center">
                        <Zap className="h-4 w-4 mr-2" />
                        {currentLicense.api_access ? 'API Access' : 'No API Access'}
                      </div>
                    </div>
                    {currentLicense.trial_expires && (
                      <div className="flex items-center text-sm">
                        <Calendar className="h-4 w-4 mr-2 text-orange-500" />
                        <span className="text-orange-600 font-medium">
                          Trial expires in {getDaysRemaining(currentLicense.trial_expires)} days
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-600 mb-1">Active</div>
                  <div className="text-sm text-gray-500">
                    Created {new Date(currentLicense.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Generate Deployment */}
              <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg shadow-lg text-white p-6">
                <h3 className="text-xl font-semibold mb-2">Generate Deployment Package</h3>
                <p className="text-blue-100 mb-4">
                  Create your customized deployment package with your license included
                </p>
                <button
                  onClick={handleGoToTemplateEditor}
                  className="inline-flex items-center px-4 py-2 bg-white text-blue-600 rounded-lg font-medium hover:bg-blue-50 transition-colors"
                >
                  Open Template Editor
                  <ArrowRight className="h-4 w-4 ml-2" />
                </button>
              </div>

              {/* Upgrade Plan */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-xl font-semibold mb-2 text-gray-900">Need More Features?</h3>
                <p className="text-gray-600 mb-4">
                  Upgrade to access more databases, API access, and premium features
                </p>
                <Link
                  to="/customer/select-tier"
                  className="inline-flex items-center px-4 py-2 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
                >
                  View Plans
                  <ExternalLink className="h-4 w-4 ml-2" />
                </Link>
              </div>
            </div>

            {/* License Details */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">License Details</h3>
              
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Features Included</h4>
                  <ul className="space-y-2 text-sm text-gray-600">
                    <li>✓ Database connections: {currentLicense.database_limit || 'Unlimited'}</li>
                    <li>{currentLicense.api_access ? '✓' : '✗'} API Access</li>
                    <li>{currentLicense.custom_integrations ? '✓' : '✗'} Custom Integrations</li>
                    <li>✓ Natural language queries</li>
                    <li>✓ Visualization generation</li>
                  </ul>
                </div>
                
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">License Information</h4>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-gray-600">License ID:</dt>
                      <dd className="text-gray-900 font-mono">
                        {currentLicense.id.substring(0, 8)}...
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-600">Plan:</dt>
                      <dd className="text-gray-900">{getTierDisplayName(currentLicense.tier)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-600">Status:</dt>
                      <dd className="text-green-600 font-medium">Active</dd>
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
              <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Settings className="h-12 w-12 text-blue-600" />
              </div>
              
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                Welcome to Ceneca License Portal
              </h2>
              <p className="text-gray-600 mb-8">
                Get started by selecting a plan and generating your first license
              </p>
              
              <Link
                to="/customer/select-tier"
                className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                Choose Your Plan
                <ArrowRight className="h-5 w-5 ml-2" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}