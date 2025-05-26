'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

// Type definitions
interface ShopInfo {
  name: string;
  domain: string;
  email: string;
}

interface SuccessResponse {
  success: true;
  shop: string;
  shopInfo: ShopInfo;
  scopes: string[];
  credentialsPath: string;
  message: string;
}

interface ErrorResponse {
  success: false;
  error: string;
  shop: string;
}

type CallbackResponse = SuccessResponse | ErrorResponse;

export default function ShopifyCallbackPage() {
  const searchParams = useSearchParams();
  const [response, setResponse] = useState<CallbackResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const code = searchParams.get('code');
        const state = searchParams.get('state');
        const shop = searchParams.get('shop');
        const error = searchParams.get('error');

        // Handle OAuth errors
        if (error) {
          setResponse({
            success: false,
            error: `OAuth Error: ${error}`,
            shop: shop || 'unknown'
          });
          setLoading(false);
          return;
        }

        // Validate required parameters
        if (!code || !shop || !state) {
          setResponse({
            success: false,
            error: 'Missing required OAuth parameters (code, shop, or state)',
            shop: shop || 'unknown'
          });
          setLoading(false);
          return;
        }

        // Call our API route to handle the token exchange
        const apiResponse = await fetch('/api/shopify/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code,
            state,
            shop,
          }),
        });

        const data = await apiResponse.json();
        setResponse(data);
      } catch (error) {
        console.error('Callback error:', error);
        setResponse({
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          shop: 'unknown'
        });
      } finally {
        setLoading(false);
      }
    };

    handleCallback();
  }, [searchParams]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-lg text-gray-600">Processing Shopify authorization...</p>
        </div>
      </div>
    );
  }

  if (!response) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-lg text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!response.success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full mx-auto p-6 text-center">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h1 className="text-2xl font-bold text-red-600 mb-4">❌ Authentication Failed</h1>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <p className="text-sm"><strong>Shop:</strong> {response.shop}</p>
              <p className="text-sm"><strong>Error:</strong> {response.error}</p>
            </div>
            <p className="text-gray-600 mb-6">
              Please try the authentication process again or contact support if the problem persists.
            </p>
            <button 
              onClick={() => window.close()} 
              className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors"
            >
              Close Window
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-2xl w-full mx-auto p-6">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <h1 className="text-3xl font-bold text-green-600 mb-6">🎉 Successfully Connected!</h1>
          
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6 text-left">
            <h2 className="text-xl font-semibold mb-4">Shop Details:</h2>
            <div className="space-y-2">
              <p><strong>Name:</strong> {response.shopInfo.name}</p>
              <p><strong>Domain:</strong> {response.shopInfo.domain}</p>
              <p><strong>Email:</strong> {response.shopInfo.email}</p>
            </div>
            
            <h3 className="text-lg font-semibold mt-6 mb-3">Granted Permissions:</h3>
            <div className="grid grid-cols-2 gap-2">
              {response.scopes.map((scope: string) => (
                <div key={scope} className="text-sm bg-green-100 px-2 py-1 rounded">
                  {scope.replace('read_', '').replace('_', ' ')}
                </div>
              ))}
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold mb-3">✅ What's Next?</h3>
            <p className="text-gray-700 mb-3">Your Shopify store is now connected to Ceneca! You can:</p>
            <ul className="text-left text-sm space-y-1 inline-block">
              <li>• Ask questions about your orders, products, and customers</li>
              <li>• Get analytics and insights from your store data</li>
              <li>• Monitor real-time changes via webhooks</li>
            </ul>
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
            <p className="text-sm"><strong>Credentials saved to:</strong></p>
            <code className="text-xs bg-gray-200 px-2 py-1 rounded mt-1 inline-block">
              {response.credentialsPath}
            </code>
          </div>

          <button 
            onClick={() => window.close()} 
            className="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 transition-colors font-semibold"
          >
            Close Window & Start Using Ceneca
          </button>
        </div>
      </div>
    </div>
  );
} 