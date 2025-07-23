import { useQuery } from '@tanstack/react-query'
import { 
  Download, 
  FileKey,
  Calendar,
  CheckCircle,
  Copy,
  ExternalLink,
  FileText,
  Shield,
  Clock,
  AlertCircle
} from 'lucide-react'
import { useState } from 'react'
import { licenseApi } from '../../services/api'
import toast from 'react-hot-toast'

export default function Downloads() {
  const [selectedLicense, setSelectedLicense] = useState<string | null>(null)
  
  // Mock customer ID - in real app this would come from auth
  const customerId = "4891c1ae-df14-4959-9d05-49015c7621da"

  const { data: licensesData } = useQuery({
    queryKey: ['customer-licenses', customerId],
    queryFn: () => licenseApi.getLicenses(0, 100, customerId),
  })

  const licenses = licensesData?.data || []

  const handleDownloadLicense = async (licenseId: string) => {
    try {
      const response = await licenseApi.getLicenseToken(licenseId)
      
      // Create downloadable file
      const licenseContent = {
        license_token: response.data.license_token,
        license_id: response.data.license_id,
        expires_at: response.data.expires_at,
        downloaded_at: new Date().toISOString()
      }
      
      const blob = new Blob([JSON.stringify(licenseContent, null, 2)], { 
        type: 'application/json' 
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `license-${licenseId.substring(0, 8)}.json`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      toast.success('License file downloaded successfully!')
    } catch (error) {
      toast.error('Failed to download license file')
    }
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Copied to clipboard!')
    } catch (error) {
      toast.error('Failed to copy to clipboard')
    }
  }

  const getStatusIcon = (license: any) => {
    if (!license.is_active) return <AlertCircle className="h-5 w-5 text-red-500" />
    
    if (license.expiration_date) {
      const expDate = new Date(license.expiration_date)
      const now = new Date()
      const daysUntilExpiry = Math.ceil((expDate.getTime() - now.getTime()) / (1000 * 3600 * 24))
      
      if (daysUntilExpiry <= 30) return <Clock className="h-5 w-5 text-orange-500" />
    }
    
    return <CheckCircle className="h-5 w-5 text-green-500" />
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Downloads</h1>
        <p className="mt-1 text-gray-600">
          Download license files and view installation instructions
        </p>
      </div>

      {/* Installation Guide */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex">
          <div className="flex-shrink-0">
            <FileText className="h-5 w-5 text-blue-400" />
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">
              Installation Instructions
            </h3>
            <div className="mt-2 text-sm text-blue-700">
              <ol className="list-decimal list-inside space-y-1">
                <li>Download your license file using the buttons below</li>
                <li>Place the license file in your application's license directory</li>
                <li>Restart your application to load the new license</li>
                <li>Verify the license status in your application's settings</li>
              </ol>
            </div>
            <div className="mt-4">
              <div className="flex">
                <button className="text-blue-600 hover:text-blue-500 text-sm font-medium flex items-center">
                  <ExternalLink className="h-4 w-4 mr-1" />
                  View detailed documentation
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* License Downloads */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium leading-6 text-gray-900 mb-6">
            Available License Downloads
          </h3>
          
          {licenses.length > 0 ? (
            <div className="space-y-4">
              {licenses.map((license) => (
                <div 
                  key={license.id} 
                  className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="flex-shrink-0">
                        <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                          <FileKey className="h-5 w-5 text-blue-600" />
                        </div>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center space-x-2">
                          <p className="text-sm font-medium text-gray-900">
                            {license.product_sku} - {license.edition_tier}
                          </p>
                          {getStatusIcon(license)}
                        </div>
                        <p className="text-sm text-gray-500">
                          {license.license_type} • Created {new Date(license.created_at).toLocaleDateString()}
                        </p>
                        {license.expiration_date && (
                          <p className="text-sm text-gray-500">
                            Expires: {new Date(license.expiration_date).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setSelectedLicense(selectedLicense === license.id ? null : license.id)}
                        className="text-gray-400 hover:text-gray-600 p-2 rounded"
                        title="View details"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDownloadLicense(license.id)}
                        disabled={!license.is_active}
                        className={`inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md ${
                          license.is_active 
                            ? 'text-white bg-blue-600 hover:bg-blue-700' 
                            : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                        }`}
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Download
                      </button>
                    </div>
                  </div>
                  
                  {/* License Details */}
                  {selectedLicense === license.id && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        <div>
                          <dt className="text-sm font-medium text-gray-500">License ID</dt>
                          <dd className="mt-1 flex items-center">
                            <span className="text-sm text-gray-900 font-mono">
                              {license.id.substring(0, 8)}...
                            </span>
                            <button
                              onClick={() => copyToClipboard(license.id)}
                              className="ml-2 text-gray-400 hover:text-gray-600"
                            >
                              <Copy className="h-4 w-4" />
                            </button>
                          </dd>
                        </div>
                        
                        <div>
                          <dt className="text-sm font-medium text-gray-500">Issue Date</dt>
                          <dd className="mt-1 text-sm text-gray-900">
                            {new Date(license.issue_date).toLocaleDateString()}
                          </dd>
                        </div>
                        
                        <div>
                          <dt className="text-sm font-medium text-gray-500">Support Tier</dt>
                          <dd className="mt-1 text-sm text-gray-900">
                            {license.support_tier || 'Standard'}
                          </dd>
                        </div>
                        
                        {license.user_limit && (
                          <div>
                            <dt className="text-sm font-medium text-gray-500">User Limit</dt>
                            <dd className="mt-1 text-sm text-gray-900">
                              {license.user_limit} users
                            </dd>
                          </div>
                        )}
                        
                        {license.node_limit && (
                          <div>
                            <dt className="text-sm font-medium text-gray-500">Node Limit</dt>
                            <dd className="mt-1 text-sm text-gray-900">
                              {license.node_limit} nodes
                            </dd>
                          </div>
                        )}
                        
                        <div>
                          <dt className="text-sm font-medium text-gray-500">Binding Type</dt>
                          <dd className="mt-1 text-sm text-gray-900 capitalize">
                            {license.binding_type}
                          </dd>
                        </div>
                      </div>
                      
                      {Object.keys(license.feature_flags).length > 0 && (
                        <div className="mt-4">
                          <dt className="text-sm font-medium text-gray-500 mb-2">Enabled Features</dt>
                          <dd className="flex flex-wrap gap-2">
                            {Object.entries(license.feature_flags).map(([feature, enabled]) => (
                              enabled && (
                                <span
                                  key={feature}
                                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
                                >
                                  <CheckCircle className="h-3 w-3 mr-1" />
                                  {feature.replace(/_/g, ' ')}
                                </span>
                              )
                            ))}
                          </dd>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <FileKey className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No licenses available</h3>
              <p className="mt-1 text-sm text-gray-500">
                Contact your administrator to request a license.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Help Section */}
      <div className="bg-gray-50 rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Need Help?
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex items-start space-x-3">
            <Shield className="flex-shrink-0 h-5 w-5 text-blue-500 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-gray-900">License Issues</p>
              <p className="text-sm text-gray-600">
                Having trouble with license validation or installation?
              </p>
              <button className="mt-2 text-sm text-blue-600 hover:text-blue-500 font-medium">
                Contact Support →
              </button>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <FileText className="flex-shrink-0 h-5 w-5 text-green-500 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-gray-900">Documentation</p>
              <p className="text-sm text-gray-600">
                Step-by-step guides for license installation and management.
              </p>
              <button className="mt-2 text-sm text-green-600 hover:text-green-500 font-medium">
                View Docs →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}