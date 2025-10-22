import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Check, ArrowRight, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '../services/api'
import { Plan } from '../types'

const PLANS: Plan[] = [
  {
    name: 'starter',
    display_name: 'Starter',
    max_seats: 5,
    monthly_price: 2000, // $20.00 per seat
    features: ['basic_queries', 'visualizations'],
    description: 'For small teams getting started with data analysis',
  },
  {
    name: 'business',
    display_name: 'Business',
    max_seats: 25,
    monthly_price: 10000, // $100.00 per seat
    features: ['basic_queries', 'visualizations', 'api_access', 'advanced_queries'],
    description: 'For growing businesses with more complex needs',
    popular: true,
  },
  {
    name: 'enterprise',
    display_name: 'Enterprise',
    max_seats: 999,
    monthly_price: 25000, // $250.00 per seat
    features: [
      'basic_queries',
      'visualizations',
      'api_access',
      'advanced_queries',
      'custom_integrations',
      'priority_support'
    ],
    description: 'For large organizations with specific requirements',
  },
]

export function PlansPage() {
  const [customerId, setCustomerId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const id = sessionStorage.getItem('ceneca_customer_id')
    if (id) {
      setCustomerId(id)
    }
  }, [])

  const handleSelectPlan = async (planName: string) => {
    if (!customerId) {
      toast.error('Customer ID required')
      return
    }

    if (planName === 'enterprise') {
      // For enterprise, redirect to contact
      window.open('https://cal.com/hardik-srivastava-riptu0/15min', '_blank')
      return
    }

    setIsGenerating(planName)
    
    try {
      const license = await apiClient.createLicense({
        customer_id: customerId,
        plan: planName,
        trial_days: 14
      })
      
      toast.success(`${planName.charAt(0).toUpperCase() + planName.slice(1)} license generated!`)
      
      // Navigate to license detail page
      navigate(`/license/${license.id}`)
      
    } catch (error) {
      console.error('License generation error:', error)
      toast.error('Failed to generate license')
    } finally {
      setIsGenerating(null)
    }
  }

  const formatPrice = (priceInCents: number) => {
    return `$${(priceInCents / 100).toFixed(0)}`
  }

  const formatFeature = (feature: string) => {
    return feature.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  return (
    <div className="min-h-screen">
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
                  Choose Your Plan
                </h1>
                <p className="text-gray-600 font-baskerville">
                  Select the plan that best fits your needs
                </p>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <div className="bg-gradient-to-b from-white to-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-6 gradient-text font-baskerville">
              Simple, Transparent Pricing
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto font-baskerville">
              Start your 14-day free trial and get instant access to your on-premise license
            </p>
          </div>

          {/* Pricing Cards */}
          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                className={`relative card transition-all duration-300 hover:scale-105 ${
                  plan.popular 
                    ? 'ring-2 ring-primary shadow-xl' 
                    : 'hover:shadow-xl'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <div className="bg-primary text-white px-4 py-1 rounded-full text-sm font-medium font-baskerville">
                      Most Popular
                    </div>
                  </div>
                )}
                
                <div className={`${plan.popular ? 'pt-4' : ''}`}>
                  {/* Header */}
                  <div className="text-center mb-8">
                    <h3 className="text-2xl font-bold mb-2 font-baskerville">{plan.display_name}</h3>
                    <div className="text-4xl font-bold mb-2 font-baskerville">
                      {formatPrice(plan.monthly_price)}
                      <span className="text-lg text-gray-500">/month/seat</span>
                    </div>
                    <p className="text-gray-600 font-baskerville">{plan.description}</p>
                  </div>

                  {/* Features */}
                  <ul className="space-y-4 mb-8">
                    <li className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 shrink-0 mt-0.5 mr-3" />
                      <span className="font-baskerville">
                        Up to {plan.max_seats === 999 ? 'unlimited' : plan.max_seats} seats
                      </span>
                    </li>
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start">
                        <Check className="h-5 w-5 text-green-500 shrink-0 mt-0.5 mr-3" />
                        <span className="font-baskerville">{formatFeature(feature)}</span>
                      </li>
                    ))}
                    <li className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 shrink-0 mt-0.5 mr-3" />
                      <span className="font-baskerville">7-day offline grace period</span>
                    </li>
                    <li className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 shrink-0 mt-0.5 mr-3" />
                      <span className="font-baskerville">Usage telemetry & analytics</span>
                    </li>
                  </ul>

                  {/* CTA Button */}
                  <button
                    onClick={() => handleSelectPlan(plan.name)}
                    disabled={isGenerating === plan.name}
                    className={`w-full btn text-lg ${
                      plan.popular
                        ? 'btn-primary shadow-lg hover:shadow-xl'
                        : 'btn-secondary'
                    } ${isGenerating === plan.name ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {isGenerating === plan.name ? (
                      <>
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                        <span>Generating License...</span>
                      </>
                    ) : (
                      <>
                        <span>
                          {plan.name === 'enterprise' ? 'Contact Sales' : 'Start 14-Day Free Trial'}
                        </span>
                        <ArrowRight className="h-5 w-5 ml-2" />
                      </>
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Benefits */}
          <div className="mt-20 text-center">
            <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
              <div>
                <div className="text-3xl font-bold text-primary mb-2 font-baskerville">14-Day</div>
                <div className="text-gray-600 font-baskerville">Free trial on all plans</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-primary mb-2 font-baskerville">Instant</div>
                <div className="text-gray-600 font-baskerville">License generation & deployment</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-primary mb-2 font-baskerville">No Setup</div>
                <div className="text-gray-600 font-baskerville">Deploy immediately with Docker</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}