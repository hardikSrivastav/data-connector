import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { 
  Shield, 
  Home,
  FileKey, 
  BarChart3, 
  Download,
  Settings,
  LogOut,
  User
} from 'lucide-react'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/customer/', icon: Home },
  { name: 'My Licenses', href: '/customer/licenses', icon: FileKey },
  { name: 'Usage Analytics', href: '/customer/analytics', icon: BarChart3 },
  { name: 'Downloads', href: '/customer/downloads', icon: Download },
]

interface CustomerLayoutProps {
  children: React.ReactNode
  customerName?: string
  customerEmail?: string
}

export default function CustomerLayout({ children, customerName = "Test Company", customerEmail = "test@example.com" }: CustomerLayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg">
        <div className="flex h-full flex-col border-r border-gray-200 bg-white">
          <div className="flex flex-1 flex-col overflow-y-auto pt-5 pb-4">
            {/* Logo */}
            <div className="flex flex-shrink-0 items-center px-4">
              <Shield className="h-8 w-8 text-blue-600" />
              <span className="ml-2 text-xl font-bold text-gray-900">
                Customer Portal
              </span>
            </div>

            {/* Customer Info */}
            <div className="mt-8 px-4">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                    <User className="h-5 w-5 text-blue-600" />
                  </div>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-900">{customerName}</p>
                  <p className="text-xs text-gray-500">{customerEmail}</p>
                </div>
              </div>
            </div>

            {/* Navigation */}
            <nav className="mt-8 flex-1 space-y-1 bg-white px-2">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={clsx(
                      isActive
                        ? 'bg-blue-100 border-r-4 border-blue-500 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                      'group flex items-center rounded-md py-2 px-2 text-sm font-medium'
                    )}
                  >
                    <item.icon
                      className={clsx(
                        isActive
                          ? 'text-blue-500'
                          : 'text-gray-400 group-hover:text-gray-500',
                        'mr-3 h-5 w-5 flex-shrink-0'
                      )}
                      aria-hidden="true"
                    />
                    {item.name}
                  </Link>
                )
              })}
            </nav>

            {/* Footer Actions */}
            <div className="border-t border-gray-200 pt-4 px-2">
              <button className="group flex w-full items-center rounded-md py-2 px-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900">
                <Settings className="mr-3 h-5 w-5 flex-shrink-0 text-gray-400 group-hover:text-gray-500" />
                Settings
              </button>
              <button className="group flex w-full items-center rounded-md py-2 px-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900">
                <LogOut className="mr-3 h-5 w-5 flex-shrink-0 text-gray-400 group-hover:text-gray-500" />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="ml-64">
        <div className="flex flex-1 flex-col">
          {/* Top navigation */}
          <div className="flex h-16 items-center border-b border-gray-200 bg-white px-8 shadow-sm">
            <div className="flex flex-1 items-center justify-between">
              <h1 className="text-lg font-semibold text-gray-900">
                License Management Portal
              </h1>
              <div className="text-sm text-gray-500">
                Last updated: {new Date().toLocaleDateString()}
              </div>
            </div>
          </div>

          {/* Page content */}
          <main className="flex-1 bg-gray-50">
            <div className="py-8 px-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}