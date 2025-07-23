import { useQuery } from '@tanstack/react-query'
import { 
  FileKey, 
  Calendar, 
  Download,
  Eye,
  MoreHorizontal,
  CheckCircle,
  XCircle,
  Clock,
  Users,
  Server,
  Zap,
  Plus
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { licenseApi } from '../../services/api'

export default function MyLicenses() {
  // Mock customer ID - in real app this would come from auth
  const customerId = "4891c1ae-df14-4959-9d05-49015c7621da"

  const { data: licensesData } = useQuery({
    queryKey: ['customer-licenses', customerId],
    queryFn: () => licenseApi.getLicenses(0, 100, customerId),
  })

  const licenses = licensesData?.data || []

  const getStatusIcon = (license: any) => {
    if (!license.is_active) return <XCircle className="h-5 w-5 text-red-500" />
    
    if (license.expiration_date) {
      const expDate = new Date(license.expiration_date)
      const now = new Date()
      const daysUntilExpiry = Math.ceil((expDate.getTime() - now.getTime()) / (1000 * 3600 * 24))
      
      if (daysUntilExpiry <= 30) return <Clock className="h-5 w-5 text-orange-500" />
    }
    
    return <CheckCircle className="h-5 w-5 text-green-500" />
  }

  const getStatusText = (license: any) => {
    if (!license.is_active) return { text: 'Inactive', color: 'bg-red-100 text-red-800' }
    
    if (license.expiration_date) {
      const expDate = new Date(license.expiration_date)
      const now = new Date()
      const daysUntilExpiry = Math.ceil((expDate.getTime() - now.getTime()) / (1000 * 3600 * 24))
      
      if (daysUntilExpiry <= 0) return { text: 'Expired', color: 'bg-red-100 text-red-800' }
      if (daysUntilExpiry <= 30) return { text: 'Expiring Soon', color: 'bg-orange-100 text-orange-800' }
    }
    
    return { text: 'Active', color: 'bg-green-100 text-green-800' }
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My Licenses</h1>
          <p className="mt-1 text-gray-600">
            Manage and monitor your software licenses
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-sm text-gray-500">
            {licenses.length} license{licenses.length !== 1 ? 's' : ''} total
          </div>
          <Link
            to="/customer/licenses/request"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Plus className="h-4 w-4 mr-2" />
            Request New License
          </Link>
        </div>
      </div>

      {/* License Summary Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <CheckCircle className="h-6 w-6 text-green-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Active Licenses</dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {licenses.filter(l => l.is_active).length}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Clock className="h-6 w-6 text-orange-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Expiring Soon</dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {licenses.filter(l => {
                      if (!l.expiration_date) return false
                      const expDate = new Date(l.expiration_date)
                      const thirtyDaysFromNow = new Date()
                      thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30)
                      return expDate <= thirtyDaysFromNow
                    }).length}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <FileKey className="h-6 w-6 text-blue-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Total Licenses</dt>
                  <dd className="text-lg font-medium text-gray-900">{licenses.length}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Licenses Table */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
            License Details
          </h3>
          
          {licenses.length > 0 ? (
            <div className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Product
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Expires
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Limits
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {licenses.map((license) => {
                      const status = getStatusText(license)
                      return (
                        <tr key={license.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <div className="flex-shrink-0 h-10 w-10">
                                <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                                  <FileKey className="h-5 w-5 text-blue-600" />
                                </div>
                              </div>
                              <div className="ml-4">
                                <div className="text-sm font-medium text-gray-900">
                                  {license.product_sku}
                                </div>
                                <div className="text-sm text-gray-500">
                                  {license.edition_tier} • {license.license_type}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              {getStatusIcon(license)}
                              <span className={`ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.color}`}>
                                {status.text}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {license.expiration_date 
                              ? new Date(license.expiration_date).toLocaleDateString()
                              : 'Never'
                            }
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            <div className="space-y-1">
                              {license.user_limit && (
                                <div className="flex items-center">
                                  <Users className="h-4 w-4 mr-1" />
                                  {license.user_limit} users
                                </div>
                              )}
                              {license.node_limit && (
                                <div className="flex items-center">
                                  <Server className="h-4 w-4 mr-1" />
                                  {license.node_limit} nodes
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div className="flex items-center space-x-2">
                              <button className="text-blue-600 hover:text-blue-900 p-1 rounded">
                                <Eye className="h-4 w-4" />
                              </button>
                              <button className="text-green-600 hover:text-green-900 p-1 rounded">
                                <Download className="h-4 w-4" />
                              </button>
                              <button className="text-gray-400 hover:text-gray-600 p-1 rounded">
                                <MoreHorizontal className="h-4 w-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <FileKey className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No licenses</h3>
              <p className="mt-1 text-sm text-gray-500">
                You don't have any licenses yet. Request your first license to get started.
              </p>
              <div className="mt-6">
                <Link
                  to="/customer/licenses/request"
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Request New License
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}