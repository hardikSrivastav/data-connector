# Shopify Integration with Ceneca Client App

## Overview

The Shopify OAuth callback functionality has been successfully integrated into the main Ceneca client application (Next.js). This allows for a seamless authentication flow that eliminates the need for manual token entry.

## Architecture

```
[CLI Command] → [OAuth URL] → [Shopify Auth] → [Client App Callback] → [Credentials Saved]
     ↓              ↓              ↓              ↓                      ↓
1. User runs auth   2. Browser      3. User        4. Auto token         5. Ready to use
   command             opens OAuth     authorizes     exchange & save       Shopify data
```

## Recent Improvements ✨

### Better Error Handling
- **Missing Credentials**: Now provides clear guidance when credentials don't exist
- **Environment Detection**: Automatically detects development vs production environment  
- **Helpful Messages**: Shows exactly what commands to run when authentication is needed

### Environment Configuration
- **Automatic Redirect URI**: Chooses correct callback URL based on environment
- **Development**: Uses `http://localhost:3000/shopify/callback`
- **Production**: Uses `https://ceneca.ai/shopify/callback`
- **Both URLs configured** in Shopify app settings for seamless switching

## Files Created/Modified

### New Files Created:
- `client/src/app/shopify/callback/page.tsx` - OAuth callback page (client-side)
- `client/src/app/api/shopify/callback/route.ts` - OAuth token exchange API (server-side)
- `client/shopify-setup.md` - Setup instructions
- `client/README-shopify.md` - This documentation
- `test_shopify_config.py` - Configuration verification script

### Modified Files:
- `ceneca-shopify/app/routes/shopify.callback.tsx` - Fixed TypeScript errors
- `ceneca-shopify/shopify.app.toml` - Added localhost redirect URL
- `config.yaml` - Added environment-specific redirect URIs
- `server/agent/config/settings.py` - Added redirect URI configuration
- `server/agent/db/adapters/shopify.py` - Improved error messages
- `server/agent/cmd/query.py` - Added environment detection for redirect URIs

## Setup Instructions

### 1. Verify Configuration

Run the configuration test script:
```bash
python test_shopify_config.py
```

This will show you:
- Current Shopify configuration
- Environment detection (dev vs prod)
- Missing configuration items
- Next steps

### 2. Environment Configuration

Create a `.env.local` file in the `client` directory:

```bash
# Create the environment file
touch client/.env.local
```

Add your Shopify app credentials:

```env
# Shopify App Configuration
SHOPIFY_APP_CLIENT_ID=44f329c8e1e82b0c891cacdb9a87862f
SHOPIFY_APP_CLIENT_SECRET=YOUR_ACTUAL_CLIENT_SECRET_HERE
```

### 3. Get Your Shopify Client Secret

1. Go to your [Shopify Partner Dashboard](https://partners.shopify.com/)
2. Navigate to your app (should be "ceneca-test" or similar)
3. Click on "App setup"
4. Copy the "Client secret" value
5. Replace `YOUR_ACTUAL_CLIENT_SECRET_HERE` in your `.env.local` file

### 4. Start the Client App

```bash
cd client
npm run dev
```

The app will run on `http://localhost:3000` by default.

## Testing the Integration

### Method 1: Full Authentication Flow (Recommended)

1. **Verify configuration**:
   ```bash
   python test_shopify_config.py
   ```

2. **Start the client app**:
   ```bash
   cd client && npm run dev
   ```

3. **Test connection first** (should show helpful message):
   ```bash
   cd server/agent
   python cli.py test-connection --type shopify
   ```
   
   You should see:
   ```
   💡 No Shopify credentials found. Run 'python cli.py authenticate shopify --shop your-store' to get started.
   ```

4. **Run authentication**:
   ```bash
   python cli.py authenticate shopify --shop ceneca-test
   ```

5. **Complete OAuth flow**:
   - Browser opens to Shopify OAuth URL
   - Authorize the app in Shopify
   - Redirected to `http://localhost:3000/shopify/callback`
   - Credentials automatically saved
   - Success page displayed

6. **Test connection again**:
   ```bash
   python cli.py test-connection --type shopify
   ```
   
   You should now see:
   ```
   ✅ Successfully connected to Shopify shop: ceneca-test.myshopify.com
   ```

### Method 2: Configuration Testing

Test the callback page directly:
```
http://localhost:3000/shopify/callback?code=test&state=test&shop=ceneca-test.myshopify.com
```

This will show an error (since the code is fake), but verifies the page loads correctly.

## Security Features

- **Client Secret Protection**: The Shopify client secret is never exposed to the browser
- **Server-Side Token Exchange**: Token exchange happens in the Next.js API route
- **Local Credential Storage**: Credentials are stored in `~/.data-connector/shopify_credentials.json`
- **State Parameter Validation**: OAuth state parameter is validated for security
- **Environment Detection**: Automatically uses correct URLs for dev/prod
- **Error Handling**: Comprehensive error handling for various failure scenarios

## OAuth Flow Details

### 1. **Authorization URL Generation** (Environment-Aware):
   ```
   # Development
   https://{shop}/admin/oauth/authorize?
     client_id={client_id}&
     scope={scopes}&
     redirect_uri=http://localhost:3000/shopify/callback&
     state={session_id}
   
   # Production  
   https://{shop}/admin/oauth/authorize?
     client_id={client_id}&
     scope={scopes}&
     redirect_uri=https://ceneca.ai/shopify/callback&
     state={session_id}
   ```

### 2. **Token Exchange** (Server-side):
   ```javascript
   POST https://{shop}/admin/oauth/access_token
   {
     "client_id": "...",
     "client_secret": "...",
     "code": "..."
   }
   ```

### 3. **Credential Storage**:
   ```json
   {
     "shops": {
       "ceneca-test.myshopify.com": {
         "access_token": "...",
         "shop_info": {
           "name": "Ceneca Test",
           "domain": "ceneca-test.myshopify.com",
           "email": "..."
         },
         "scopes": ["read_orders", "read_products", ...],
         "last_updated": "2025-01-28T...",
         "api_version": "2025-04"
       }
     }
   }
   ```

## Granted Permissions

The authentication flow requests the following Shopify permissions:

- **Orders**: `read_orders`, `read_all_orders`, `read_draft_orders`
- **Products**: `read_products`, `read_inventory`
- **Customers**: `read_customers`
- **Analytics**: `read_analytics`, `read_reports`
- **Fulfillment**: `read_fulfillments`, `read_assigned_fulfillment_orders`
- **Shipping**: `read_shipping`, `read_locations`
- **Marketing**: `read_marketing_events`, `read_price_rules`, `read_discounts`
- **Other**: `read_checkouts`, `read_gift_cards`, `read_themes`, `read_translations`

## Troubleshooting

### Common Issues

1. **"No Shopify credentials found"** ✅ **IMPROVED**
   - **Old**: Confusing error with no guidance
   - **New**: Clear message with exact command to run
   - **Solution**: Run `python cli.py authenticate shopify --shop your-store`

2. **"Server configuration error: Missing app credentials"**
   - Make sure `.env.local` exists in the `client` directory
   - Verify `SHOPIFY_APP_CLIENT_SECRET` is set correctly
   - Run `python test_shopify_config.py` to verify

3. **"Token exchange failed"**
   - Check that your Shopify app redirect URIs include both:
     - `http://localhost:3000/shopify/callback` (development)
     - `https://ceneca.ai/shopify/callback` (production)
   - Verify the shop domain is correct

4. **"Connection failed!"** ✅ **FIXED**
   - **Old**: Generic error message
   - **New**: Specific guidance based on the failure reason
   - Check if authentication is needed or if credentials are invalid

### Development vs Production

The system now automatically detects the environment:

- **Development**: Uses `http://localhost:3000/shopify/callback`
- **Production**: Uses `https://ceneca.ai/shopify/callback`
- **Manual Override**: Set `SHOPIFY_REDIRECT_URI` in config to force a specific URL

## Next Steps

After successful authentication, you can:

1. **Query your Shopify data**:
   ```bash
   python cli.py query --type shopify "How many orders did I get last week?"
   ```

2. **Test the connection**:
   ```bash
   python cli.py test-connection --type shopify
   ```

3. **Build the search index**:
   ```bash
   python cli.py build-index --type shopify
   ```

## Benefits of This Integration

1. **No Manual Token Entry**: Fully automated OAuth flow
2. **Secure**: Client secret protected server-side
3. **User-Friendly**: Clear success/error pages with helpful information
4. **Consistent**: Uses the same credential storage as other adapters
5. **Environment-Aware**: Automatically works in both dev and production
6. **Self-Diagnosing**: Clear error messages guide users to solutions
7. **Production-Ready**: Works seamlessly across different environments

The integration now provides a professional, secure, and user-friendly authentication experience that gracefully handles missing credentials and guides users through the setup process. 