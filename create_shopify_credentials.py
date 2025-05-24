#!/usr/bin/env python3
"""
Helper script to manually create Shopify credentials
"""
import json
import os
from pathlib import Path

def create_shopify_credentials():
    """Create Shopify credentials file manually"""
    
    print("🛍️  Shopify Credentials Setup")
    print("=" * 40)
    
    # Get input from user
    shop_domain = input("Enter your shop domain (e.g., ceneca-test): ").strip()
    if not shop_domain.endswith('.myshopify.com'):
        shop_domain = f"{shop_domain}.myshopify.com"
    
    access_token = input("Enter your access token: ").strip()
    
    if not access_token:
        print("❌ Access token is required!")
        return False
    
    # Create credentials directory
    credentials_dir = Path.home() / '.data-connector'
    credentials_dir.mkdir(exist_ok=True)
    
    # Create credentials structure
    credentials = {
        'shops': {
            shop_domain: {
                'access_token': access_token,
                'shop_info': {
                    'name': shop_domain.replace('.myshopify.com', '').title(),
                    'domain': shop_domain
                },
                'last_updated': '2024-01-01T00:00:00Z',
                'api_version': '2025-04'
            }
        }
    }
    
    # Save credentials
    credentials_path = credentials_dir / 'shopify_credentials.json'
    with open(credentials_path, 'w') as f:
        json.dump(credentials, f, indent=2)
    
    print(f"✅ Credentials saved to: {credentials_path}")
    print(f"🛍️  Shop: {shop_domain}")
    print("\nYou can now test the connection with:")
    print("python -m agent.cmd.query test-connection --type shopify")
    
    return True

if __name__ == "__main__":
    create_shopify_credentials() 