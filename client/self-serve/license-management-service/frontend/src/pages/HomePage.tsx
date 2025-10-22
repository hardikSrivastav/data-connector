import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Shield, Users, BarChart } from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '../services/api'

export function HomePage() {
  const [email, setEmail] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  const handleGetStarted = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !companyName) {
      toast.error('Please fill in all fields')
      return
    }

    setIsLoading(true)
    try {
      const customer = await apiClient.createCustomer({
        company_name: companyName,
        contact_email: email,
      })
      
      toast.success('Welcome to Ceneca!')
      
      // Store customer ID for session
      sessionStorage.setItem('ceneca_customer_id', customer.id)
      navigate('/dashboard')
      
    } catch (error) {
      console.error('Error creating customer:', error)
      toast.error('Failed to create account. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleExistingCustomer = () => {
    const customerId = prompt('Enter your Customer ID:')
    if (customerId) {
      sessionStorage.setItem('ceneca_customer_id', customerId)
      navigate('/dashboard')
    }
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="text-2xl font-bold text-primary font-baskerville">
              Ceneca License Portal
            </div>
            <button
              onClick={handleExistingCustomer}
              className="text-gray-600 hover:text-primary font-baskerville"
            >
              Existing Customer?
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="bg-gradient-to-b from-white to-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-5xl md:text-6xl font-bold mb-6 gradient-text font-baskerville">
              Simplified On-Premise Licensing
            </h1>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-12 font-baskerville">
              Get your Ceneca license, deploy on-premise, and track usage with built-in telemetry. 
              Perfect for enterprises that need control over their data.
            </p>

            {/* Quick Start Form */}
            <div className="max-w-md mx-auto">
              <form onSubmit={handleGetStarted} className="space-y-4">
                <input
                  type="text"
                  placeholder="Company Name"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="input w-full"
                  required
                />
                <input
                  type="email"
                  placeholder="Contact Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input w-full"
                  required
                />
                <button
                  type="submit"
                  disabled={isLoading}
                  className="btn btn-primary w-full text-lg"
                >
                  {isLoading ? (
                    'Creating Account...'
                  ) : (
                    <>
                      Get Started Free
                      <ArrowRight className="h-5 w-5 ml-2" />
                    </>
                  )}
                </button>
              </form>
              <p className="text-sm text-gray-500 mt-4 font-baskerville">
                Start with a 14-day free trial • No credit card required
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-gray-900 mb-4 font-baskerville">
              Everything You Need for On-Premise Licensing
            </h2>
            <p className="text-xl text-gray-600 font-baskerville">
              Simple, transparent, and built for enterprise deployment
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Per-Seat Billing */}
            <div className="card text-center">
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Users className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-3 font-baskerville">Per-Seat Billing</h3>
              <p className="text-gray-600 font-baskerville">
                Pay only for active users. Automatic usage tracking with 7-day offline grace period.
              </p>
            </div>

            {/* Usage Telemetry */}
            <div className="card text-center">
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <BarChart className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-3 font-baskerville">Usage Analytics</h3>
              <p className="text-gray-600 font-baskerville">
                Detailed telemetry and analytics dashboard. Track features, users, and system performance.
              </p>
            </div>

            {/* Enterprise Security */}
            <div className="card text-center">
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-3 font-baskerville">Enterprise Ready</h3>
              <p className="text-gray-600 font-baskerville">
                JWT-based licensing, Docker deployment, and self-service management portal.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-gray-900 py-16">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-white mb-4 font-baskerville">
            Ready to Deploy Ceneca On-Premise?
          </h2>
          <p className="text-xl text-gray-300 mb-8 font-baskerville">
            Get your license in minutes and start your 14-day free trial today.
          </p>
          <button
            onClick={() => document.querySelector('input')?.focus()}
            className="btn btn-primary text-lg"
          >
            Start Free Trial
            <ArrowRight className="h-5 w-5 ml-2" />
          </button>
        </div>
      </div>
    </div>
  )
}