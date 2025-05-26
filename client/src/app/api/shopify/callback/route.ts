import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import os from 'os';

// Type definitions
interface ShopInfo {
  name: string;
  domain: string;
  email: string;
}

interface ShopCredentials {
  access_token: string;
  shop_info: ShopInfo;
  scopes: string[];
  granted_scopes: string[]; // Actually granted scopes from OAuth
  requested_scopes: string[]; // All scopes from TOML file
  last_updated: string;
  api_version: string;
}

interface CredentialsFile {
  shops: Record<string, ShopCredentials>;
}

interface SuccessResponse {
  success: true;
  shop: string;
  shopInfo: ShopInfo;
  scopes: string[];
  grantedScopes: string[];
  requestedScopes: string[];
  credentialsPath: string;
  message: string;
}

interface ErrorResponse {
  success: false;
  error: string;
  shop: string;
}

/**
 * Parse shopify.app.toml file to extract all defined scopes
 */
function parseShopifyAppToml(): string[] {
  try {
    // Look for the TOML file in the ceneca-shopify directory
    const possiblePaths = [
      path.join(process.cwd(), '..', 'ceneca-shopify', 'shopify.app.toml'),
      path.join(process.cwd(), 'ceneca-shopify', 'shopify.app.toml'),
      path.join(__dirname, '..', '..', '..', '..', '..', 'ceneca-shopify', 'shopify.app.toml'),
      // Add more potential paths as needed
    ];

    let tomlContent = '';
    let tomlPath = '';

    for (const filePath of possiblePaths) {
      if (fs.existsSync(filePath)) {
        tomlContent = fs.readFileSync(filePath, 'utf8');
        tomlPath = filePath;
        break;
      }
    }

    if (!tomlContent) {
      console.log('⚠️ shopify.app.toml not found, using fallback scopes');
      // Fallback to the scopes we know from the TOML file (updated to match corrected TOML)
      return [
        'read_orders', 'read_products', 'read_customers', 'read_inventory',
        'read_locations', 'read_price_rules', 'read_discounts', 'read_analytics',
        'read_reports', 'read_checkouts', 'read_draft_orders', 'read_fulfillments',
        'read_gift_cards', 'read_marketing_events', 'read_order_edits',
        'read_payment_terms', 'read_shipping', 'read_themes', 'read_translations',
        'read_assigned_fulfillment_orders', 'read_merchant_managed_fulfillment_orders',
        'read_third_party_fulfillment_orders', 'write_assigned_fulfillment_orders',
        'write_merchant_managed_fulfillment_orders', 'write_third_party_fulfillment_orders',
        'write_products'
      ];
    }

    console.log(`📖 Found shopify.app.toml at: ${tomlPath}`);

    // Simple TOML parsing for scopes section
    // Look for the scopes = """ ... """ block
    const scopesMatch = tomlContent.match(/scopes\s*=\s*"""\s*([\s\S]*?)\s*"""/);
    
    if (!scopesMatch) {
      console.log('⚠️ No scopes section found in TOML file');
      return [];
    }

    const scopesText = scopesMatch[1];
    
    // Parse the scopes - they're comma-separated and may span multiple lines
    const scopes = scopesText
      .split(',')
      .map(scope => scope.trim())
      .filter(scope => scope.length > 0)
      .map(scope => scope.replace(/["\n\r]/g, '').trim());

    console.log(`✅ Parsed ${scopes.length} scopes from TOML file:`, scopes);
    return scopes;

  } catch (error) {
    console.error('❌ Error parsing shopify.app.toml:', error);
    return [];
  }
}

export async function POST(request: NextRequest) {
  console.log('🚀 Shopify OAuth callback started');
  
  try {
    const { code, state, shop } = await request.json();
    console.log('📨 Received OAuth parameters:', { code: code?.substring(0, 10) + '...', state, shop });

    // Validate required parameters
    if (!code || !shop || !state) {
      console.log('❌ Missing required parameters');
      return NextResponse.json<ErrorResponse>({
        success: false,
        error: 'Missing required OAuth parameters (code, shop, or state)',
        shop: shop || 'unknown'
      }, { status: 400 });
    }

    // Get app credentials from environment variables
    const clientId = process.env.SHOPIFY_APP_CLIENT_ID;
    const clientSecret = process.env.SHOPIFY_APP_CLIENT_SECRET;
    
    console.log('🔑 App credentials check:', { 
      clientId: clientId ? clientId.substring(0, 8) + '...' : 'MISSING',
      clientSecret: clientSecret ? 'SET' : 'MISSING' 
    });
    
    if (!clientId || !clientSecret) {
      console.log('❌ Missing app credentials');
      return NextResponse.json<ErrorResponse>({
        success: false,
        error: 'Server configuration error: Missing app credentials',
        shop
      }, { status: 500 });
    }

    // Parse all scopes from TOML file
    const requestedScopes = parseShopifyAppToml();

    // Exchange authorization code for access token
    console.log('🔄 Exchanging authorization code for access token...');
    const tokenResponse = await fetch(`https://${shop}/admin/oauth/access_token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        code: code,
      }),
    });

    if (!tokenResponse.ok) {
      const errorText = await tokenResponse.text();
      console.log('❌ Token exchange failed:', tokenResponse.status, errorText);
      throw new Error(`Token exchange failed: ${tokenResponse.status} ${errorText}`);
    }

    const tokenData = await tokenResponse.json();
    const accessToken = tokenData.access_token;
    const grantedScopesString = tokenData.scope;
    
    // Parse granted scopes
    const grantedScopes = grantedScopesString ? grantedScopesString.split(',').map((s: string) => s.trim()) : [];
    
    console.log('✅ Token exchange successful:', { 
      accessToken: accessToken ? accessToken.substring(0, 10) + '...' : 'MISSING',
      grantedScopes: grantedScopes.length,
      requestedScopes: requestedScopes.length
    });

    // Log scope comparison
    const missingScopes = requestedScopes.filter(scope => !grantedScopes.includes(scope));
    if (missingScopes.length > 0) {
      console.log('⚠️ Some requested scopes were not granted:', missingScopes);
    }

    if (!accessToken) {
      console.log('❌ No access token in response');
      throw new Error('No access token received from Shopify');
    }

    // Get shop information
    console.log('🏪 Fetching shop information...');
    const shopInfoResponse = await fetch(`https://${shop}/admin/api/2025-04/shop.json`, {
      headers: {
        'X-Shopify-Access-Token': accessToken,
      },
    });

    let shopInfo: ShopInfo = {
      name: shop.replace('.myshopify.com', '').replace('-', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
      domain: shop,
      email: 'unknown@example.com'
    };

    if (shopInfoResponse.ok) {
      const shopData = await shopInfoResponse.json();
      shopInfo = {
        name: shopData.shop.name || shopInfo.name,
        domain: shopData.shop.domain || shop,
        email: shopData.shop.email || shopInfo.email
      };
      console.log('✅ Shop info retrieved:', shopInfo);
    } else {
      console.log('⚠️ Could not fetch shop info, using defaults');
    }

    // Save credentials to user's data directory
    const credentialsDir = path.join(os.homedir(), '.data-connector');
    const credentialsPath = path.join(credentialsDir, 'shopify_credentials.json');
    
    console.log('💾 Preparing to save credentials to:', credentialsPath);
    
    // Ensure directory exists
    if (!fs.existsSync(credentialsDir)) {
      console.log('📁 Creating credentials directory:', credentialsDir);
      fs.mkdirSync(credentialsDir, { recursive: true });
    } else {
      console.log('📁 Credentials directory exists');
    }
    
    // Load existing credentials or create new structure
    let credentials: CredentialsFile = { shops: {} };
    if (fs.existsSync(credentialsPath)) {
      try {
        const existingData = fs.readFileSync(credentialsPath, 'utf8');
        credentials = JSON.parse(existingData);
        console.log('📖 Loaded existing credentials file with shops:', Object.keys(credentials.shops || {}));
      } catch (error) {
        console.warn('⚠️ Could not parse existing credentials file, creating new one:', error);
      }
    } else {
      console.log('📝 Creating new credentials file');
    }

    // Add/update shop credentials with both granted and requested scopes
    credentials.shops[shop] = {
      access_token: accessToken,
      shop_info: shopInfo,
      scopes: requestedScopes, // Use all requested scopes as the main scopes array
      granted_scopes: grantedScopes, // Track what was actually granted
      requested_scopes: requestedScopes, // Track what was requested
      last_updated: new Date().toISOString(),
      api_version: '2025-04'
    };

    console.log('💾 Saving credentials for shop:', shop);
    console.log('📊 Updated credentials structure:', {
      shops: Object.keys(credentials.shops),
      currentShop: {
        hasToken: !!credentials.shops[shop].access_token,
        requestedScopes: credentials.shops[shop].requested_scopes.length,
        grantedScopes: credentials.shops[shop].granted_scopes.length,
        lastUpdated: credentials.shops[shop].last_updated
      }
    });

    // Save updated credentials
    try {
      fs.writeFileSync(credentialsPath, JSON.stringify(credentials, null, 2));
      console.log('✅ Credentials saved successfully');
      
      // Verify the file was written correctly
      if (fs.existsSync(credentialsPath)) {
        const fileStats = fs.statSync(credentialsPath);
        console.log('📊 File verification:', {
          exists: true,
          size: fileStats.size,
          modified: fileStats.mtime
        });
        
        // Double-check by reading the file back
        const verifyData = fs.readFileSync(credentialsPath, 'utf8');
        const verifyCredentials = JSON.parse(verifyData);
        console.log('🔍 Verification read:', {
          hasShop: shop in verifyCredentials.shops,
          hasToken: !!verifyCredentials.shops[shop]?.access_token
        });
      } else {
        console.log('❌ File does not exist after write');
      }
    } catch (writeError) {
      console.error('❌ Error writing credentials file:', writeError);
      throw writeError;
    }

    console.log('🎉 OAuth callback completed successfully');
    
    return NextResponse.json<SuccessResponse>({
      success: true,
      shop,
      shopInfo,
      scopes: requestedScopes, // Return all requested scopes
      grantedScopes: grantedScopes, // Also return what was actually granted
      requestedScopes: requestedScopes, // Explicit field for requested scopes
      credentialsPath,
      message: 'Successfully connected to Shopify!'
    });

  } catch (error) {
    console.error('💥 OAuth callback error:', error);
    return NextResponse.json<ErrorResponse>({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
      shop: 'unknown'
    }, { status: 500 });
  }
} 