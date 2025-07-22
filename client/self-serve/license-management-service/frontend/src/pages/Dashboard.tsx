import { useQuery } from '@tanstack/react-query'
import { 
  Users, 
  FileKey, 
  Activity, 
  AlertTriangle,
  TrendingUp,
  CheckCircle
} from 'lucide-react'
import { healthApi, licenseApi, customerApi } from '../services/api'

export default function Dashboard() {
  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.checkHealth(),
    refetchInterval: 30000, // Refetch every 30 seconds
  })

  const { data: licenseData } = useQuery({
    queryKey: ['licenses', 'dashboard'],
    queryFn: () => licenseApi.getLicenses(0, 1000),
  })

  const { data: customerData } = useQuery({
    queryKey: ['customers', 'dashboard'],
    queryFn: () => customerApi.getCustomers(0, 1000),
  })

  const licenses = licenseData?.data || []
  const customers = customerData?.data || []

  const stats = [
    {
      name: 'Total Customers',
      value: customers.length,
      icon: Users,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 dark:bg-blue-900',
    },
    {
      name: 'Active Licenses',
      value: licenses.filter(l => l.is_active).length,
      icon: FileKey,
      color: 'text-green-600',
      bgColor: 'bg-green-50 dark:bg-green-900',
    },
    {
      name: 'Expired Licenses',
      value: licenses.filter(l => {
        if (!l.expiration_date) return false
        return new Date(l.expiration_date) < new Date()
      }).length,
      icon: AlertTriangle,
      color: 'text-red-600',
      bgColor: 'bg-red-50 dark:bg-red-900',
    },
    {
      name: 'System Health',
      value: healthData?.data?.status === 'healthy' ? 'Healthy' : 'Unhealthy',
      icon: CheckCircle,
      color: healthData?.data?.status === 'healthy' ? 'text-green-600' : 'text-red-600',
      bgColor: healthData?.data?.status === 'healthy' ? 'bg-green-50 dark:bg-green-900' : 'bg-red-50 dark:bg-red-900',
    },
  ]

  const recentLicenses = licenses
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  return (
    <div className="space-y-8">      
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          Dashboard
        </h1>
        <p className="mt-1 text-gray-600">
          Overview of your license management system
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="relative overflow-hidden rounded-lg bg-white px-4 pt-5 pb-12 shadow-sm border border-gray-200 sm:px-6 sm:pt-6"
          >
            <dt>
              <div className={`absolute rounded-md p-3 bg-gray-50`}>
                <stat.icon
                  className={`h-6 w-6 ${stat.color}`}
                  aria-hidden="true"
                />
              </div>
              <p className="ml-16 truncate text-sm font-medium text-gray-600">
                {stat.name}
              </p>
            </dt>
            <dd className="ml-16 flex items-baseline pb-6 sm:pb-7">
              <p className="text-2xl font-semibold text-gray-900">
                {stat.value}
              </p>
            </dd>
          </div>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Recent Licenses */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium leading-6 text-gray-900">
              Recent Licenses
            </h3>
            <div className="mt-5">
              <div className="flow-root">
                <ul className="-my-5 divide-y divide-gray-200">
                  {recentLicenses.length > 0 ? (
                    recentLicenses.map((license) => (
                      <li key={license.id} className="py-4">
                        <div className="flex items-center space-x-4">
                          <div className="flex-shrink-0">
                            <FileKey className="h-8 w-8 text-gray-400" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900">
                              {license.product_sku} - {license.edition_tier}
                            </p>
                            <p className="truncate text-sm text-gray-500">
                              {license.license_type} • Created {new Date(license.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <div>
                            <span
                              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                license.is_active
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {license.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </div>
                        </div>
                      </li>
                    ))
                  ) : (
                    <li className="py-4 text-center text-sm text-gray-500">
                      No licenses found
                    </li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium leading-6 text-gray-900">
              System Status
            </h3>
            <div className="mt-5 space-y-4">
              <div className="flex items-center">
                <CheckCircle 
                  className={`h-5 w-5 ${
                    healthData?.data?.status === 'healthy' 
                      ? 'text-green-500' 
                      : 'text-red-500'
                  }`} 
                />
                <span className="ml-2 text-sm text-gray-600">
                  API Service: {healthData?.data?.status || 'Unknown'}
                </span>
              </div>
              
              <div className="flex items-center">
                <Activity className="h-5 w-5 text-blue-500" />
                <span className="ml-2 text-sm text-gray-600">
                  Database: Connected
                </span>
              </div>
              
              <div className="flex items-center">
                <TrendingUp className="h-5 w-5 text-green-500" />
                <span className="ml-2 text-sm text-gray-600">
                  License Generation: Operational
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}