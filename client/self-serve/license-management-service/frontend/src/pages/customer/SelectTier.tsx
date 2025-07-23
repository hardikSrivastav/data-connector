import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

interface TierConfig {
  name: string
  price: string
  description: string
  features: string[]
  highlighted?: boolean
}

const tiers: TierConfig[] = [
  {
    name: "Starter",
    price: "$20/month/person",
    description: "For small teams getting started with data analysis",
    features: [
      "Connect up to 3 databases",
      "Natural language queries", 
      "Visualization generation",
      "Basic integrations",
      "Email support"
    ]
  },
  {
    name: "Business", 
    price: "$100/month/person",
    description: "For growing businesses with more complex needs",
    features: [
      "Connect up to 10 databases",
      "Advanced natural language queries",
      "Custom visualization templates", 
      "API access",
      "All integrations",
      "Priority support",
      "User management"
    ],
    highlighted: true
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For large organizations with specific requirements", 
    features: [
      "Unlimited database connections",
      "Custom model training",
      "Advanced security features",
      "Dedicated support team", 
      "SLA guarantees",
      "Custom integrations",
      "On-premise deployment options"
    ]
  }
]

export default function SelectTier() {
  const [isGenerating, setIsGenerating] = useState<string | null>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Mock customer ID - in real app this would come from auth
  const customerId = "4891c1ae-df14-4959-9d05-49015c7621da"

  const generateLicense = async (tier: string) => {
    const response = await fetch('http://localhost:8010/api/licenses/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        customer_id: customerId,
        tier: tier.toLowerCase() 
      })
    })

    if (!response.ok) {
      throw new Error('Failed to generate license')
    }

    return response.json()
  }

  const handleStartTrial = async (tierName: string) => {
    if (tierName === 'Enterprise') {
      // For enterprise, redirect to contact
      window.open('https://cal.com/hardik-srivastava-riptu0/15min', '_blank')
      return
    }

    setIsGenerating(tierName)
    
    try {
      const license = await generateLicense(tierName)
      toast.success(`${tierName} trial license generated!`)
      
      // Redirect to template editor with license
      window.location.href = `http://localhost:8500?license=${license.license_token}`
      
    } catch (error) {
      console.error('License generation error:', error)
      toast.error('Failed to generate license')
    } finally {
      setIsGenerating(null)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-white via-gray-50 to-gray-100 py-20">
      <div className="container mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-purple-600 to-blue-800">
            Choose Your Plan
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Start your 14-day free trial and generate your deployment package instantly
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative rounded-2xl shadow-xl overflow-hidden transition-all duration-300 hover:scale-105 ${
                tier.highlighted 
                  ? 'ring-2 ring-purple-500 bg-white' 
                  : 'bg-white hover:shadow-2xl'
              }`}
            >
              {tier.highlighted && (
                <div className="absolute top-0 left-0 right-0 bg-purple-500 text-white py-2 text-center text-sm font-medium">
                  Most Popular
                </div>
              )}
              
              <div className={`p-8 ${tier.highlighted ? 'pt-12' : ''}`}>
                {/* Header */}
                <div className="text-center mb-8">
                  <h3 className="text-2xl font-bold text-gray-900 mb-2">{tier.name}</h3>
                  <div className="text-4xl font-bold text-gray-900 mb-2">{tier.price}</div>
                  <p className="text-gray-600">{tier.description}</p>
                </div>

                {/* Features */}
                <ul className="space-y-4 mb-8">
                  {tier.features.map((feature, index) => (
                    <li key={index} className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 shrink-0 mt-0.5 mr-3" />
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>

                {/* CTA Button */}
                <button
                  onClick={() => handleStartTrial(tier.name)}
                  disabled={isGenerating === tier.name}
                  className={`w-full py-4 px-6 rounded-xl font-semibold text-lg transition-all duration-300 flex items-center justify-center space-x-2 ${
                    tier.highlighted
                      ? 'bg-purple-600 text-white hover:bg-purple-700 shadow-lg hover:shadow-xl'
                      : 'bg-gray-900 text-white hover:bg-gray-800'
                  } ${isGenerating === tier.name ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {isGenerating === tier.name ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                      <span>Generating License...</span>
                    </>
                  ) : (
                    <>
                      <span>
                        {tier.name === 'Enterprise' ? 'Contact Sales' : 'Start 14-Day Free Trial'}
                      </span>
                      <ArrowRight className="h-5 w-5" />
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
              <div className="text-3xl font-bold text-purple-600 mb-2">14-Day</div>
              <div className="text-gray-600">Free trial on all plans</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-purple-600 mb-2">Instant</div>
              <div className="text-gray-600">License generation & deployment</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-purple-600 mb-2">No Setup</div>
              <div className="text-gray-600">Deploy immediately after trial</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}