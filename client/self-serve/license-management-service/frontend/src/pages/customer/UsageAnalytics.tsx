import { useQuery } from '@tanstack/react-query'
import { 
  BarChart3, 
  TrendingUp,
  Activity,
  Clock,
  Users,
  Cpu,
  HardDrive,
  Zap,
  Calendar,
  Download
} from 'lucide-react'

export default function UsageAnalytics() {
  // Mock data - in real app this would come from API
  const mockUsageData = {
    totalRequests: 15420,
    activeUsers: 47,
    dataProcessed: "2.3 TB",
    avgResponseTime: "125ms",
    peakConcurrent: 89,
    systemUptime: "99.9%"
  }

  const monthlyUsage = [
    { month: 'Jan', usage: 1200, users: 35 },
    { month: 'Feb', usage: 1890, users: 42 },
    { month: 'Mar', usage: 2340, users: 51 },
    { month: 'Apr', usage: 1980, users: 47 },
    { month: 'May', usage: 2100, users: 53 },
    { month: 'Jun', usage: 2450, users: 48 },
  ]

  const featureUsage = [
    { feature: 'User Authentication', usage: 98, color: 'bg-blue-500' },
    { feature: 'Data Processing', usage: 84, color: 'bg-green-500' },
    { feature: 'API Requests', usage: 76, color: 'bg-yellow-500' },
    { feature: 'File Storage', usage: 65, color: 'bg-purple-500' },
    { feature: 'Analytics', usage: 43, color: 'bg-pink-500' },
  ]

  const stats = [
    {
      name: 'Total Requests',
      value: mockUsageData.totalRequests.toLocaleString(),
      icon: Activity,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      change: '+12% from last month'
    },
    {
      name: 'Active Users',
      value: mockUsageData.activeUsers,
      icon: Users,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      change: '+5 new this month'
    },
    {
      name: 'Data Processed',
      value: mockUsageData.dataProcessed,
      icon: HardDrive,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
      change: '+18% from last month'
    },
    {
      name: 'Avg Response Time',
      value: mockUsageData.avgResponseTime,
      icon: Zap,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      change: '15ms improvement'
    },
  ]

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Usage Analytics</h1>
          <p className="mt-1 text-gray-600">
            Monitor your software usage and performance metrics
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
            <Calendar className="h-4 w-4 mr-2" />
            Last 30 days
          </button>
          <button className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
            <Download className="h-4 w-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Usage Stats */}
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

      {/* Charts and Analytics */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Usage Trend Chart */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
              Monthly Usage Trend
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm text-gray-500">
                <span>Requests (thousands)</span>
                <span>Active Users</span>
              </div>
              
              {/* Simple bar chart representation */}
              <div className="space-y-3">
                {monthlyUsage.map((month, index) => (
                  <div key={month.month} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{month.month}</span>
                      <div className="flex space-x-4">
                        <span className="text-blue-600">{(month.usage/1000).toFixed(1)}k</span>
                        <span className="text-green-600">{month.users}</span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <div className="flex-1 bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-500 h-2 rounded-full" 
                          style={{width: `${(month.usage / 2500) * 100}%`}}
                        ></div>
                      </div>
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-green-500 h-2 rounded-full" 
                          style={{width: `${(month.users / 60) * 100}%`}}
                        ></div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Feature Usage */}
        <div className="bg-white shadow-sm rounded-lg border border-gray-200">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
              Feature Usage
            </h3>
            <div className="space-y-4">
              {featureUsage.map((feature) => (
                <div key={feature.feature} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium text-gray-900">{feature.feature}</span>
                    <span className="text-gray-500">{feature.usage}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${feature.color}`} 
                      style={{width: `${feature.usage}%`}}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* System Performance */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium leading-6 text-gray-900 mb-6">
            System Performance
          </h3>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div className="text-center">
              <div className="flex justify-center">
                <div className="relative w-24 h-24">
                  <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 36 36">
                    <path
                      className="text-gray-200"
                      stroke="currentColor"
                      strokeWidth="3"
                      fill="transparent"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="text-green-500"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeDasharray="99.9, 100"
                      strokeLinecap="round"
                      fill="transparent"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xl font-semibold text-gray-900">99.9%</span>
                  </div>
                </div>
              </div>
              <p className="mt-2 text-sm font-medium text-gray-900">System Uptime</p>
              <p className="text-sm text-gray-500">Last 30 days</p>
            </div>

            <div className="text-center">
              <div className="flex justify-center">
                <div className="relative w-24 h-24">
                  <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 36 36">
                    <path
                      className="text-gray-200"
                      stroke="currentColor"
                      strokeWidth="3"
                      fill="transparent"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="text-blue-500"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeDasharray="75, 100"
                      strokeLinecap="round"
                      fill="transparent"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xl font-semibold text-gray-900">75%</span>
                  </div>
                </div>
              </div>
              <p className="mt-2 text-sm font-medium text-gray-900">CPU Usage</p>
              <p className="text-sm text-gray-500">Average</p>
            </div>

            <div className="text-center">
              <div className="flex justify-center">
                <div className="relative w-24 h-24">
                  <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 36 36">
                    <path
                      className="text-gray-200"
                      stroke="currentColor"
                      strokeWidth="3"
                      fill="transparent"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="text-purple-500"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeDasharray="60, 100"
                      strokeLinecap="round"
                      fill="transparent"
                      d="M18 2.0845
                        a 15.9155 15.9155 0 0 1 0 31.831
                        a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xl font-semibold text-gray-900">60%</span>
                  </div>
                </div>
              </div>
              <p className="mt-2 text-sm font-medium text-gray-900">Memory Usage</p>
              <p className="text-sm text-gray-500">Current</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}