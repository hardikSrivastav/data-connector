import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { 
  ArrowLeft,
  Download,
  Copy,
  CheckCircle,
  Terminal,
  FileText,
  ExternalLink
} from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '../services/api'

export function LicenseDetailPage() {
  const { licenseId } = useParams<{ licenseId: string }>()

  const { data: license, isLoading } = useQuery({
    queryKey: ['license', licenseId],
    queryFn: () => apiClient.getLicense(licenseId!),
    enabled: !!licenseId,
  })

  const { data: downloadData } = useQuery({
    queryKey: ['license-download', licenseId],
    queryFn: () => apiClient.downloadLicense(licenseId!),
    enabled: !!licenseId,
  })

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    toast.success(`${label} copied to clipboard!`)
  }

  const downloadLicenseFile = () => {
    if (!downloadData) return

    const licenseContent = {
      license_key: downloadData.license_key,
      jwt_token: downloadData.jwt_token,
      plan: downloadData.plan,
      max_seats: downloadData.max_seats,
      features: downloadData.features,
    }

    const blob = new Blob([JSON.stringify(licenseContent, null, 2)], {
      type: 'application/json',
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ceneca-license-${downloadData.license_key}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    toast.success('License file downloaded!')
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-600 font-baskerville">Loading license details...</p>
        </div>
      </div>
    )
  }

  if (!license) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4 font-baskerville">License Not Found</h2>
          <Link to="/dashboard" className="btn btn-primary">
            Return to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  const isTrialActive = license.trial_expires_at && new Date(license.trial_expires_at) > new Date()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <Link to="/dashboard" className="mr-4">
                <ArrowLeft className="h-5 w-5 text-gray-600 hover:text-primary" />
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-primary font-baskerville">
                  License Details
                </h1>
                <p className="text-gray-600 font-baskerville">
                  {license.license_key}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              {license.is_active ? (
                <div className="flex items-center text-green-600">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  <span className="font-baskerville">Active</span>
                </div>
              ) : (
                <div className="text-gray-500 font-baskerville">Inactive</div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* License Status Card */}
          <div className="card">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-semibold font-baskerville">
                  {license.plan.charAt(0).toUpperCase() + license.plan.slice(1)} License
                </h2>
                <p className="text-gray-600 font-baskerville">
                  Up to {license.max_seats} concurrent users
                </p>
              </div>
              <div className="text-right">
                {isTrialActive ? (
                  <div>
                    <div className="text-lg font-bold text-orange-600 font-baskerville">Trial Active</div>
                    <div className="text-sm text-gray-500 font-baskerville">
                      Expires {new Date(license.trial_expires_at!).toLocaleDateString()}
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="text-lg font-bold text-green-600 font-baskerville">Licensed</div>
                    <div className="text-sm text-gray-500 font-baskerville">
                      Valid until {new Date(license.expires_at).toLocaleDateString()}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h3 className="font-medium mb-3 font-baskerville">Features Included</h3>
                <ul className="space-y-2 text-sm text-gray-600">
                  {license.features.map((feature) => (
                    <li key={feature} className="flex items-center font-baskerville">
                      <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
                      {feature.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </li>
                  ))}
                </ul>
              </div>
              
              <div>
                <h3 className="font-medium mb-3 font-baskerville">License Details</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-600 font-baskerville">License Key:</dt>
                    <dd className="font-mono text-xs">{license.license_key}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-600 font-baskerville">Created:</dt>
                    <dd className="font-baskerville">{new Date(license.created_at).toLocaleDateString()}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-600 font-baskerville">Max Seats:</dt>
                    <dd className="font-baskerville">{license.max_seats}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>

          {/* Download Section */}
          <div className="card">
            <h2 className="text-xl font-semibold mb-4 font-baskerville">Download & Deploy</h2>
            <p className="text-gray-600 mb-6 font-baskerville">
              Get your license file and deployment instructions to start using Ceneca on-premise.
            </p>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Download License File */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center mb-3">
                  <FileText className="h-5 w-5 text-primary mr-2" />
                  <h3 className="font-medium font-baskerville">License File</h3>
                </div>
                <p className="text-sm text-gray-600 mb-4 font-baskerville">
                  JSON file containing your license key and JWT token
                </p>
                <button
                  onClick={downloadLicenseFile}
                  className="btn btn-primary w-full"
                  disabled={!downloadData}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download License File
                </button>
              </div>

              {/* Quick Deploy */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center mb-3">
                  <Terminal className="h-5 w-5 text-primary mr-2" />
                  <h3 className="font-medium font-baskerville">Quick Deploy</h3>
                </div>
                <p className="text-sm text-gray-600 mb-4 font-baskerville">
                  One-command deployment with Docker
                </p>
                <button
                  onClick={() => window.open('http://localhost:8500', '_blank')}
                  className="btn btn-secondary w-full"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open Template Editor
                </button>
              </div>
            </div>
          </div>

          {/* Deployment Instructions */}
          {downloadData && (
            <div className="card">
              <h2 className="text-xl font-semibold mb-4 font-baskerville">Deployment Instructions</h2>
              
              <div className="space-y-6">
                {/* Docker Command */}
                <div>
                  <h3 className="font-medium mb-2 font-baskerville">Docker Command</h3>
                  <div className="bg-gray-900 text-white p-4 rounded-lg font-mono text-sm overflow-x-auto">
                    <div className="flex items-center justify-between">
                      <span>{downloadData.deployment_instructions.agent_command}</span>
                      <button
                        onClick={() => copyToClipboard(downloadData.deployment_instructions.agent_command, 'Docker command')}
                        className="ml-2 p-1 hover:bg-gray-800 rounded"
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Environment Variables */}
                <div>
                  <h3 className="font-medium mb-2 font-baskerville">Environment Variables</h3>
                  <div className="bg-gray-900 text-white p-4 rounded-lg font-mono text-sm overflow-x-auto">
                    <div className="flex items-start justify-between">
                      <pre className="whitespace-pre-wrap">{downloadData.deployment_instructions.docker_env}</pre>
                      <button
                        onClick={() => copyToClipboard(downloadData.deployment_instructions.docker_env, 'Environment variables')}
                        className="ml-2 p-1 hover:bg-gray-800 rounded"
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Config File */}
                <div>
                  <h3 className="font-medium mb-2 font-baskerville">Configuration File</h3>
                  <div className="bg-gray-900 text-white p-4 rounded-lg font-mono text-sm overflow-x-auto">
                    <div className="flex items-start justify-between">
                      <pre className="whitespace-pre-wrap">{downloadData.deployment_instructions.config_file}</pre>
                      <button
                        onClick={() => copyToClipboard(downloadData.deployment_instructions.config_file, 'Configuration')}
                        className="ml-2 p-1 hover:bg-gray-800 rounded"
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2 font-baskerville">Next Steps:</h4>
                <ol className="list-decimal ml-4 space-y-1 text-sm text-blue-800">
                  <li className="font-baskerville">Download the license file</li>
                  <li className="font-baskerville">Run the Docker command with your license</li>
                  <li className="font-baskerville">Access your Ceneca deployment on the configured port</li>
                  <li className="font-baskerville">Monitor usage through this portal</li>
                </ol>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}