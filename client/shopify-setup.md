# Shopify OAuth Setup for Client App

## Environment Configuration

To enable Shopify OAuth callbacks in the client application, you need to create a `.env.local` file in the `client` directory with the following configuration:

```bash
# Create the .env.local file
touch client/.env.local
```

Add the following content to `client/.env.local`:

```env
# Shopify App Configuration
SHOPIFY_APP_CLIENT_ID=44f329c8e1e82b0c891cacdb9a87862f
SHOPIFY_APP_CLIENT_SECRET=YOUR_SHOPIFY_CLIENT_SECRET_HERE
```

## Getting Your Shopify Client Secret

1. Go to your [Shopify Partner Dashboard](https://partners.shopify.com/)
2. Navigate to your app
3. Click on "App setup" 
4. Copy the "Client secret" value
5. Replace `YOUR_SHOPIFY_CLIENT_SECRET_HERE` in your `.env.local` file

## OAuth Flow

The OAuth flow now works as follows:

1. User runs `python cli.py authenticate shopify --shop your-store` (from the server/agent directory)
2. Browser opens to Shopify OAuth authorization URL  
3. User authorizes the app in Shopify
4. Shopify redirects to `https://ceneca.ai/shopify/callback` (your client app)
5. The client app exchanges the authorization code for an access token
6. Credentials are automatically saved to `~/.data-connector/shopify_credentials.json`
7. Success page is shown to the user

## Security Notes

- The client secret is never exposed to the browser
- Token exchange happens server-side in the Next.js API route
- Credentials are stored locally in the user's home directory
- The callback page is not accessible through normal navigation

## Testing

After setting up the environment variables, you can test the integration by:

1. Running the client app: `npm run dev` (from the client directory)
2. Running the authentication command from the server
3. Verifying that the callback page loads correctly at `http://localhost:3000/shopify/callback` 