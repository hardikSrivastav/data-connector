import { useQuery } from '@tanstack/react-query'
import { 
  Shield, 
  FileKey, 
  Calendar, 
  Users,
  Activity,
  AlertCircle,
  CheckCircle,
  Clock,
  Download,
  TrendingUp,
  Plus
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { licenseApi, validationApi } from '../../services/api'

export default function CustomerDashboard() {
  // Mock customer ID - in real app this would come from auth
  const customerId = "4891c1ae-df14-4959-9d05-49015c7621da"

  const { data: licensesData } = useQuery({
    queryKey: ['customer-licenses', customerId],
    queryFn: () => licenseApi.getLicenses(0, 100, customerId),
  })

  const licenses = licensesData?.data || []

  const stats = [
    {
      name: 'Active Licenses',
      value: licenses.filter(l => l.is_active).length,
      icon: Shield,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      change: '+2 from last month'
    },
    {
      name: 'Expiring Soon',
      value: licenses.filter(l => {
        if (!l.expiration_date) return false
        const expDate = new Date(l.expiration_date)
        const thirtyDaysFromNow = new Date()
        thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30)
        return expDate <= thirtyDaysFromNow
      }).length,
      icon: Clock,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      change: '2 licenses'
    },
    {
      name: 'Total Usage',
      value: '847 GB',
      icon: TrendingUp,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      change: '+12% this month'
    },
    {
      name: 'Support Incidents',
      value: '2 Open',
      icon: AlertCircle,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
      change: 'Last: 2 days ago'
    },
  ]

  const recentLicenses = licenses
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 3)

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          Welcome back!
        </h1>
        <p className="mt-1 text-gray-600">
          Here's what's happening with your licenses and usage
        </p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="relative overflow-hidden rounded-lg bg-white px-4 pt-5 pb-12 shadow-sm border border-gray-200 sm:px-6 sm:pt-6"
          >
            <dt>
              <div className={`absolute rounded-md p-3 ${stat.bgColor}`}>
                <stat.icon
                  className={`h-6 w-6 ${stat.color}`}
                  aria-hidden="true"
                />
              </div>
              <p className="ml-16 truncate text-sm font-medium text-gray-600">
                {stat.name}
              </p>
            </dt>
            <dd className="ml-16 pb-6 sm:pb-7">
              <p className="text-2xl font-semibold text-gray-900">
                {stat.value}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {stat.change}
              </p>
            </dd>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium leading-6 text-gray-900">
            Quick Actions
          </h3>
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
            <Link 
              to="/customer/licenses/request"
              className="relative flex items-center space-x-3 rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="flex-shrink-0">
                <Plus className="h-6 w-6 text-gray-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">Request License</p>
                <p className="text-sm text-gray-500">Get new software license</p>
              </div>
            </Link>

            <Link 
              to="/customer/downloads"
              className="relative flex items-center space-x-3 rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="flex-shrink-0">
                <Download className="h-6 w-6 text-gray-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">Download Licenses</p>
                <p className="text-sm text-gray-500">Get your license files</p>
              </div>
            </Link>

            <Link 
              to="/customer/analytics"
              className="relative flex items-center space-x-3 rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="flex-shrink-0">
                <Activity className="h-6 w-6 text-gray-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">View Usage</p>
                <p className="text-sm text-gray-500">Check analytics</p>
              </div>
            </Link>

            <Link 
              to="/customer/licenses"
              className="relative flex items-center space-x-3 rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="flex-shrink-0">
                <FileKey className="h-6 w-6 text-gray-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">My Licenses</p>
                <p className="text-sm text-gray-500">Manage existing licenses</p>
              </div>
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Licenses and Activity */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Your Licenses */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium leading-6 text-gray-900">
              Your Licenses
            </h3>
            <div className="mt-5">
              <div className="flow-root">
                <ul className="-my-5 divide-y divide-gray-200">
                  {recentLicenses.length > 0 ? (
                    recentLicenses.map((license) => (
                      <li key={license.id} className="py-4">
                        <div className="flex items-center space-x-4">
                          <div className="flex-shrink-0">
                            <div className={`h-2 w-2 rounded-full ${license.is_active ? 'bg-green-400' : 'bg-red-400'}`} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900">
                              {license.product_sku} - {license.edition_tier}
                            </p>
                            <p className="truncate text-sm text-gray-500">
                              Expires: {license.expiration_date ? new Date(license.expiration_date).toLocaleDateString() : 'Never'}
                            </p>
                          </div>
                          <div>
                            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              license.is_active
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
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
              <div className="mt-6">
                <button className="w-full flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                  View All Licenses
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium leading-6 text-gray-900">
              Recent Activity
            </h3>
            <div className="mt-5">
              <div className="flow-root">
                <ul className="-mb-8">
                  <li>
                    <div className="relative pb-8">
                      <span className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
                      <div className="relative flex items-start space-x-3">
                        <div>
                          <div className="relative px-1">
                            <div className="h-8 w-8 bg-blue-100 rounded-full ring-8 ring-white flex items-center justify-center">
                              <CheckCircle className="h-5 w-5 text-blue-600" />
                            </div>
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div>
                            <div className="text-sm">
                              <p className="font-medium text-gray-900">License validated successfully</p>
                            </div>
                            <p className="mt-0.5 text-sm text-gray-500">2 hours ago</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>

                  <li>
                    <div className="relative pb-8">
                      <span className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
                      <div className="relative flex items-start space-x-3">
                        <div>
                          <div className="relative px-1">
                            <div className="h-8 w-8 bg-green-100 rounded-full ring-8 ring-white flex items-center justify-center">
                              <Download className="h-5 w-5 text-green-600" />
                            </div>
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div>
                            <div className="text-sm">
                              <p className="font-medium text-gray-900">License file downloaded</p>
                            </div>
                            <p className="mt-0.5 text-sm text-gray-500">1 day ago</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>

                  <li>
                    <div className="relative">
                      <div className="relative flex items-start space-x-3">
                        <div>
                          <div className="relative px-1">
                            <div className="h-8 w-8 bg-gray-100 rounded-full ring-8 ring-white flex items-center justify-center">
                              <Users className="h-5 w-5 text-gray-600" />
                            </div>
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div>
                            <div className="text-sm">
                              <p className="font-medium text-gray-900">Account created</p>
                            </div>
                            <p className="mt-0.5 text-sm text-gray-500">3 days ago</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}