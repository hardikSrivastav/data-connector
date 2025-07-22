import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { 
  Shield, 
  Users, 
  FileKey, 
  Activity, 
  CheckCircle, 
  Settings
} from 'lucide-react'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: Activity },
  { name: 'Customers', href: '/customers', icon: Users },
  { name: 'Licenses', href: '/licenses', icon: FileKey },
  { name: 'Usage', href: '/usage', icon: Activity },
  { name: 'Validation', href: '/validation', icon: CheckCircle },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg">
        <div className="flex h-full flex-col border-r border-gray-200 bg-white">
          <div className="flex flex-1 flex-col overflow-y-auto pt-5 pb-4">
            <div className="flex flex-shrink-0 items-center px-4">
              <Shield className="h-8 w-8 text-blue-600" />
              <span className="ml-2 text-xl font-bold text-gray-900">
                License Manager
              </span>
            </div>
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
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="ml-64">
        <div className="flex flex-1 flex-col">
          {/* Top navigation */}
          <div className="flex h-16 items-center border-b border-gray-200 bg-white px-4 shadow-sm">
            <div className="flex flex-1 justify-between px-4 sm:px-6 lg:px-8">
              <div className="flex flex-1">
                <div className="flex w-full md:ml-0">
                  <div className="relative w-full text-gray-400 focus-within:text-gray-600">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center">
                      <Shield className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <h1 className="text-lg font-semibold text-gray-900 py-2 pl-8">
                      Enterprise License Management
                    </h1>
                  </div>
                </div>
              </div>
              <div className="ml-4 flex items-center">
                <button
                  type="button"
                  className="rounded-full bg-white p-1 text-gray-400 hover:text-gray-500"
                >
                  <span className="sr-only">Settings</span>
                  <Settings className="h-6 w-6" aria-hidden="true" />
                </button>
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