import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  FileKey, 
  Calendar, 
  Users,
  Server,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
  Plus
} from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { licenseApi } from '../../services/api'

interface LicenseRequestForm {
  product_sku: string
  edition_tier: string
  license_type: string
  user_limit?: number
  node_limit?: number
  feature_flags: Record<string, boolean>
  support_tier?: string
}

export default function RequestLicense() {
  const [formData, setFormData] = useState<LicenseRequestForm>({
    product_sku: '',
    edition_tier: 'standard',
    license_type: 'subscription',
    user_limit: undefined,
    node_limit: undefined,
    feature_flags: {},
    support_tier: 'standard'
  })

  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const queryClient = useQueryClient()

  // Mock customer ID - in real app this would come from auth
  const customerId = "4891c1ae-df14-4959-9d05-49015c7621da"

  const availableProducts = [
    { sku: 'CENECA_DATA_CONNECTOR', name: 'Ceneca Data Connector', description: 'Enterprise data integration platform' },
    { sku: 'CENECA_ANALYTICS', name: 'Ceneca Analytics', description: 'Advanced analytics and reporting suite' },
    { sku: 'CENECA_DASHBOARD', name: 'Ceneca Dashboard', description: 'Business intelligence dashboard' }
  ]

  const availableFeatures = [
    'api_access',
    'custom_connectors', 
    'advanced_analytics',
    'real_time_sync',
    'white_labeling',
    'priority_support',
    'custom_reports',
    'data_encryption'
  ]

  const createLicenseMutation = useMutation({
    mutationFn: async (requestData: any) => {
      // Create the license request with current date and future expiration
      const now = new Date()
      const oneYearFromNow = new Date()
      oneYearFromNow.setFullYear(now.getFullYear() + 1)

      const licenseData = {
        customer_id: customerId,
        product_sku: requestData.product_sku,
        edition_tier: requestData.edition_tier,
        license_type: requestData.license_type,
        start_date: now.toISOString(),
        expiration_date: requestData.license_type === 'perpetual' ? null : oneYearFromNow.toISOString(),
        user_limit: requestData.user_limit || null,
        node_limit: requestData.node_limit || null,
        feature_flags: requestData.feature_flags,
        support_tier: requestData.support_tier
      }

      const response = await fetch('http://localhost:8010/api/licenses/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(licenseData)
      })

      if (!response.ok) {
        throw new Error('Failed to create license')
      }

      return response.json()
    },
    onSuccess: () => {
      toast.success('License request submitted successfully!')
      queryClient.invalidateQueries({ queryKey: ['customer-licenses'] })
      // Reset form
      setFormData({
        product_sku: '',
        edition_tier: 'standard', 
        license_type: 'subscription',
        user_limit: undefined,
        node_limit: undefined,
        feature_flags: {},
        support_tier: 'standard'
      })
      setSelectedFeatures([])
    },
    onError: (error) => {
      toast.error('Failed to submit license request')
      console.error('License request error:', error)
    }
  })

  const handleFeatureToggle = (feature: string) => {
    const newFeatures = selectedFeatures.includes(feature)
      ? selectedFeatures.filter(f => f !== feature)
      : [...selectedFeatures, feature]
    
    setSelectedFeatures(newFeatures)
    
    const featureFlags = newFeatures.reduce((flags, f) => {
      flags[f] = true
      return flags
    }, {} as Record<string, boolean>)
    
    setFormData(prev => ({ ...prev, feature_flags: featureFlags }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.product_sku) {
      toast.error('Please select a product')
      return
    }

    createLicenseMutation.mutate(formData)
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <Link 
              to="/customer/licenses"
              className="text-gray-400 hover:text-gray-600"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <h1 className="text-3xl font-bold text-gray-900">Request New License</h1>
          </div>
          <p className="mt-1 text-gray-600">
            Submit a request for a new software license
          </p>
        </div>
      </div>

      {/* License Request Form */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200">
        <form onSubmit={handleSubmit} className="px-6 py-8 space-y-8">
          {/* Product Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-4">
              Select Product
            </label>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {availableProducts.map((product) => (
                <div
                  key={product.sku}
                  className={`relative rounded-lg border p-4 cursor-pointer hover:border-blue-300 ${
                    formData.product_sku === product.sku
                      ? 'border-blue-500 ring-2 ring-blue-200'
                      : 'border-gray-300'
                  }`}
                  onClick={() => setFormData(prev => ({ ...prev, product_sku: product.sku }))}
                >
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <FileKey className="h-6 w-6 text-blue-600" />
                    </div>
                    <div className="ml-3 flex-1">
                      <h3 className="text-sm font-medium text-gray-900">
                        {product.name}
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        {product.description}
                      </p>
                    </div>
                    {formData.product_sku === product.sku && (
                      <CheckCircle className="h-5 w-5 text-blue-500" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* License Configuration */}
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Edition Tier
              </label>
              <select
                value={formData.edition_tier}
                onChange={(e) => setFormData(prev => ({ ...prev, edition_tier: e.target.value }))}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="starter">Starter</option>
                <option value="standard">Standard</option>
                <option value="professional">Professional</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                License Type
              </label>
              <select
                value={formData.license_type}
                onChange={(e) => setFormData(prev => ({ ...prev, license_type: e.target.value }))}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="trial">Trial (30 days)</option>
                <option value="subscription">Subscription (1 year)</option>
                <option value="perpetual">Perpetual</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                User Limit
              </label>
              <input
                type="number"
                value={formData.user_limit || ''}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  user_limit: e.target.value ? parseInt(e.target.value) : undefined 
                }))}
                placeholder="Unlimited"
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Leave empty for unlimited users</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Node Limit
              </label>
              <input
                type="number"
                value={formData.node_limit || ''}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  node_limit: e.target.value ? parseInt(e.target.value) : undefined 
                }))}
                placeholder="Unlimited"
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Leave empty for unlimited nodes</p>
            </div>
          </div>

          {/* Feature Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-4">
              Additional Features
            </label>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {availableFeatures.map((feature) => (
                <div
                  key={feature}
                  className={`relative rounded-lg border p-3 cursor-pointer hover:border-blue-300 ${
                    selectedFeatures.includes(feature)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300'
                  }`}
                  onClick={() => handleFeatureToggle(feature)}
                >
                  <div className="flex items-center">
                    <div className={`h-4 w-4 rounded border-2 mr-2 flex items-center justify-center ${
                      selectedFeatures.includes(feature)
                        ? 'border-blue-500 bg-blue-500'
                        : 'border-gray-300'
                    }`}>
                      {selectedFeatures.includes(feature) && (
                        <CheckCircle className="h-3 w-3 text-white" />
                      )}
                    </div>
                    <span className="text-sm font-medium text-gray-900">
                      {feature.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Support Tier */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Support Tier
            </label>
            <select
              value={formData.support_tier}
              onChange={(e) => setFormData(prev => ({ ...prev, support_tier: e.target.value }))}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="basic">Basic Support</option>
              <option value="standard">Standard Support</option>
              <option value="premium">Premium Support</option>
              <option value="enterprise">Enterprise Support</option>
            </select>
          </div>

          {/* Submit Button */}
          <div className="flex items-center justify-end space-x-4">
            <Link
              to="/customer/licenses"
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={createLicenseMutation.isPending || !formData.product_sku}
              className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white ${
                createLicenseMutation.isPending || !formData.product_sku
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {createLicenseMutation.isPending ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Submitting...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Request License
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Help Section */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex">
          <div className="flex-shrink-0">
            <AlertCircle className="h-5 w-5 text-blue-400" />
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">
              License Request Process
            </h3>
            <div className="mt-2 text-sm text-blue-700">
              <ul className="list-disc list-inside space-y-1">
                <li>Your license request will be processed immediately for trial licenses</li>
                <li>Subscription and perpetual licenses may require approval</li>
                <li>You'll receive an email notification once your license is ready</li>
                <li>Downloaded licenses can be found in the Downloads section</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}