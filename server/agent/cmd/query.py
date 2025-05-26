#!/usr/bin/env python
import typer
import asyncio
import json
import os
import sys
import time
import uuid
import urllib.parse
from typing import Optional, Dict, Any, List
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from urllib.parse import urlparse
import requests
import webbrowser
import secrets
import argparse

print("Starting Data Connector CLI...")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.db.execute import test_conn
from agent.llm.client import get_llm_client
from agent.meta.ingest import SchemaSearcher, ensure_index_exists, build_and_save_index_for_db
from agent.api.endpoints import sanitize_sql
from agent.tools.tools import DataTools
from agent.tools.state_manager import StateManager
from agent.config.settings import Settings
from agent.config.config_loader import load_config, load_config_with_defaults
from agent.performance import ensure_schema_index_updated
from agent.db.db_orchestrator import Orchestrator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rich console
console = Console()

# Create typer app
app = typer.Typer(help="Data Connector CLI")

# Create auth sub-app
auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")

@auth_app.command("test")
def auth_test():
    """Test authentication configuration"""
    async def run():
        settings = Settings()
        
        console.print(f"[bold]Authentication Configuration:[/bold]")
        console.print(f"Auth Enabled: {'[green]Yes[/green]' if settings.AUTH_ENABLED else '[red]No[/red]'}")
        console.print(f"Auth Protocol: {settings.AUTH_PROTOCOL or '[dim]Not configured[/dim]'}")
        
        if settings.AUTH_PROTOCOL == 'oidc':
            console.print(f"\n[bold]OIDC Configuration:[/bold]")
            console.print(f"Provider: {settings.OIDC_PROVIDER or '[dim]Not configured[/dim]'}")
            console.print(f"Client ID: {settings.OIDC_CLIENT_ID or '[dim]Not configured[/dim]'}")
            console.print(f"Client Secret: {'[green]Configured[/green]' if settings.OIDC_CLIENT_SECRET else '[red]Not configured[/red]'}")
            console.print(f"Issuer: {settings.OIDC_ISSUER or '[dim]Not configured[/dim]'}")
            console.print(f"Discovery URL: {settings.OIDC_DISCOVERY_URL or '[dim]Not configured[/dim]'}")
            console.print(f"Redirect URI: {settings.OIDC_REDIRECT_URI or '[dim]Not configured[/dim]'}")
            
            # Show scopes
            if settings.OIDC_SCOPES:
                console.print(f"Scopes: {', '.join(settings.OIDC_SCOPES)}")
            else:
                console.print(f"Scopes: [dim]None configured[/dim]")
            
            # Show claims mapping
            if settings.OIDC_CLAIMS_MAPPING:
                console.print(f"\n[bold]Claims Mapping:[/bold]")
                for claim, attr in settings.OIDC_CLAIMS_MAPPING.items():
                    console.print(f"  {claim} → {attr}")
        
        # Show role mappings if any
        if settings.ROLE_MAPPINGS:
            console.print(f"\n[bold]Role Mappings:[/bold]")
            for group, role in settings.ROLE_MAPPINGS.items():
                console.print(f"  {group} → {role}")
        
        # Overall status
        console.print(f"\n[bold]Authentication Status:[/bold]")
        if settings.is_auth_enabled:
            console.print(f"[green]Authentication is properly configured and enabled[/green]")
        else:
            console.print(f"[yellow]Authentication is not fully configured or is disabled[/yellow]")
            
            # Provide guidance on what's missing
            if not settings.AUTH_ENABLED:
                console.print("  • Authentication is disabled in config")
            elif settings.AUTH_PROTOCOL == 'oidc':
                if not settings.OIDC_PROVIDER:
                    console.print("  • OIDC provider is not configured")
                if not settings.OIDC_CLIENT_ID:
                    console.print("  • OIDC client ID is not configured")
                if not settings.OIDC_CLIENT_SECRET:
                    console.print("  • OIDC client secret is not configured")
                if not settings.OIDC_ISSUER:
                    console.print("  • OIDC issuer is not configured")
                if not settings.OIDC_REDIRECT_URI:
                    console.print("  • OIDC redirect URI is not configured")
    
    asyncio.run(run())

@auth_app.command("login")
def auth_login():
    """Login using configured authentication provider"""
    async def run():
        settings = Settings()
        
        # Verify that auth is properly configured
        if not settings.AUTH_ENABLED:
            console.print("[red]Authentication is not enabled in config.[/red]")
            console.print("Please set 'enabled: true' in the sso section of auth-config.yaml")
            return
        
        if settings.AUTH_PROTOCOL == 'oidc':
            # Check that all required OIDC settings are present
            missing_settings = []
            if not settings.OIDC_PROVIDER:
                missing_settings.append("OIDC provider")
            if not settings.OIDC_CLIENT_ID:
                missing_settings.append("OIDC client ID")
            if not settings.OIDC_CLIENT_SECRET:
                missing_settings.append("OIDC client secret")
            if not settings.OIDC_ISSUER:
                missing_settings.append("OIDC issuer")
            if not settings.OIDC_REDIRECT_URI:
                missing_settings.append("OIDC redirect URI")
                
            if missing_settings:
                console.print("[red]Authentication is not fully configured.[/red]")
                console.print("The following settings are missing:")
                for setting in missing_settings:
                    console.print(f"  • {setting}")
                return
            
            # Generate a session ID for the auth flow
            session_id = secrets.token_urlsafe(16)
            
            # Define the redirect URI - this should match what's configured in auth-config.yaml
            redirect_uri = settings.OIDC_REDIRECT_URI
            
            # Set up the OIDC authorization parameters
            auth_params = {
                "client_id": settings.OIDC_CLIENT_ID,
                "response_type": "code",
                "scope": " ".join(settings.OIDC_SCOPES),
                "redirect_uri": redirect_uri,
                "state": session_id,
                "nonce": secrets.token_urlsafe(8)
            }
            
            # Construct the authorization URL based on the discovery URL
            auth_url = None
            
            if settings.OIDC_DISCOVERY_URL:
                try:
                    # Fetch the OpenID configuration
                    discovery_response = requests.get(settings.OIDC_DISCOVERY_URL)
                    discovery_response.raise_for_status()
                    
                    discovery_data = discovery_response.json()
                    auth_endpoint = discovery_data.get("authorization_endpoint")
                    
                    if not auth_endpoint:
                        console.print("[red]Could not find authorization endpoint in OIDC discovery document.[/red]")
                        return
                    
                    # Build the authorization URL with the parameters
                    auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(auth_params)}"
                    
                except Exception as e:
                    console.print(f"[red]Error fetching OIDC discovery document: {str(e)}[/red]")
                    return
            else:
                # Construct the URL directly from the issuer
                auth_url = f"{settings.OIDC_ISSUER}/protocol/openid-connect/auth?{urllib.parse.urlencode(auth_params)}"
            
            # Set up a local HTTP server to handle the redirect
            callback_port = int(urlparse(redirect_uri).port or 8000)
            callback_host = urlparse(redirect_uri).hostname or "localhost"
            
            # Create a temporary directory to store auth tokens
            token_dir = os.path.join(settings.get_app_dir(), "tokens")
            os.makedirs(token_dir, exist_ok=True)
            token_file = os.path.join(token_dir, f"oidc_token_{session_id}.json")
            
            # Set up a function to handle the callback
            async def handle_callback(request):
                code = request.query.get("code")
                state = request.query.get("state")
                
                if not code or state != session_id:
                    return web.Response(text="Authentication failed. Invalid state parameter.", content_type="text/html")
                
                # Exchange the code for tokens
                token_params = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.OIDC_CLIENT_ID,
                    "client_secret": settings.OIDC_CLIENT_SECRET
                }
                
                try:
                    # Get the token endpoint from discovery if available
                    token_endpoint = None
                    if settings.OIDC_DISCOVERY_URL:
                        discovery_response = requests.get(settings.OIDC_DISCOVERY_URL)
                        discovery_response.raise_for_status()
                        
                        discovery_data = discovery_response.json()
                        token_endpoint = discovery_data.get("token_endpoint")
                        
                    if not token_endpoint:
                        # Fallback to constructing from issuer
                        token_endpoint = f"{settings.OIDC_ISSUER}/protocol/openid-connect/token"
                    
                    # Exchange the code for tokens
                    token_response = requests.post(token_endpoint, data=token_params)
                    token_response.raise_for_status()
                    
                    token_data = token_response.json()
                    
                    # Save the tokens
                    with open(token_file, "w") as f:
                        json.dump(token_data, f, indent=2)
                    
                    # Get user info if possible
                    user_info = None
                    access_token = token_data.get("access_token")
                    
                    if access_token:
                        # Try to get user info endpoint from discovery
                        userinfo_endpoint = None
                        if settings.OIDC_DISCOVERY_URL:
                            discovery_data = discovery_response.json()
                            userinfo_endpoint = discovery_data.get("userinfo_endpoint")
                            
                        if userinfo_endpoint:
                            userinfo_response = requests.get(
                                userinfo_endpoint,
                                headers={"Authorization": f"Bearer {access_token}"}
                            )
                            if userinfo_response.status_code == 200:
                                user_info = userinfo_response.json()
                    
                    # Return a simple HTML response to the user
                    success_html = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Authentication Successful</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                            .success { color: green; }
                            .info { margin-top: 20px; text-align: left; display: inline-block; }
                        </style>
                    </head>
                    <body>
                        <h1 class="success">Authentication Successful!</h1>
                        <p>You have successfully authenticated with Data Connector.</p>
                        <p>You can close this window and return to the command line.</p>
                    </body>
                    </html>
                    """
                    
                    # Signal the waiting thread that auth is complete
                    auth_event.set()
                    
                    return web.Response(text=success_html, content_type="text/html")
                    
                except Exception as e:
                    error_message = f"Error exchanging code for tokens: {str(e)}"
                    console.print(f"[red]{error_message}[/red]")
                    return web.Response(text=f"<h1>Authentication Error</h1><p>{error_message}</p>", content_type="text/html")
            
            # We need aiohttp for this - check if it's available
            try:
                from aiohttp import web
            except ImportError:
                console.print("[red]The aiohttp package is required for authentication.[/red]")
                console.print("Please install it with: pip install aiohttp")
                return
            
            # Create an event to signal when auth is complete
            auth_event = asyncio.Event()
            
            # Start the web server
            app = web.Application()
            app.router.add_get(urlparse(redirect_uri).path, handle_callback)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, callback_host, callback_port)
            
            try:
                await site.start()
                
                # Open the browser
                console.print("\n" + "="*60)
                console.print(f"Opening browser for authentication...")
                console.print(f"If your browser doesn't open automatically, please visit:")
                console.print(f"\n{auth_url}\n")
                console.print("="*60 + "\n")
                
                try:
                    webbrowser.open(auth_url)
                except Exception as e:
                    console.print(f"Failed to open browser: {e}")
                    console.print(f"Please manually visit the URL above to complete authentication")
                
                # Wait for the auth to complete or timeout
                console.print("Waiting for authentication to complete in the browser...")
                
                try:
                    # Wait with a timeout
                    await asyncio.wait_for(auth_event.wait(), timeout=300)  # 5-minute timeout
                    
                    # Check if the token file exists
                    if os.path.exists(token_file):
                        with open(token_file, "r") as f:
                            token_data = json.load(f)
                        
                        # Display success message
                        console.print("\n[green]Authentication successful![/green]")
                        
                        # Show token expiry
                        if "expires_in" in token_data:
                            expires_in = token_data["expires_in"]
                            console.print(f"Token will expire in {expires_in} seconds")
                        
                        # Show scopes
                        if "scope" in token_data:
                            scopes = token_data["scope"].split()
                            console.print(f"Granted scopes: {', '.join(scopes)}")
                        
                        console.print("\nYou are now authenticated and can use protected resources.")
                    else:
                        console.print("\n[red]Authentication failed: Token file not created[/red]")
                
                except asyncio.TimeoutError:
                    console.print("\n[red]Authentication timed out after 5 minutes[/red]")
                
            finally:
                # Clean up
                await runner.cleanup()
        else:
            console.print(f"[red]Unsupported authentication protocol: {settings.AUTH_PROTOCOL}[/red]")
            console.print("Currently only 'oidc' is supported")
    
    asyncio.run(run())

@app.command()
def authenticate(
    db_type: str = typer.Argument(..., help="Database type to authenticate with ('slack', 'shopify', 'ga4', etc.)"),
    shop: Optional[str] = typer.Option(None, "--shop", help="Shop domain for Shopify (e.g., mystore.myshopify.com)")
):
    """Authenticate with a specific database/service type"""
    async def run():
        if db_type.lower() == "slack":
            # Use existing Slack auth
            class Args:
                pass
            args = Args()
            await slack_auth(args)
        elif db_type.lower() == "shopify":
            # Use Shopify auth
            class Args:
                def __init__(self):
                    self.shop = shop
            args = Args()
            await shopify_auth(args)
        else:
            console.print(f"[red]Authentication not yet implemented for {db_type}[/red]")
            console.print("Supported types: slack, shopify")
    
    asyncio.run(run())

@app.command()
def test_connection(
    db_uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)"),
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', 'qdrant', 'shopify', 'ga4', etc.)")
):
    """Test database connection"""
    async def run():
        settings = Settings()

        logger.info(f"Settings: {settings}")
        
        # Set DB_TYPE if provided
        if db_type:
            settings.DB_TYPE = db_type
            # Force reload of connection URI based on the new DB_TYPE
            # This is needed because connection_uri may have been cached with the previous DB_TYPE
            logger.info(f"Setting DB_TYPE to: {db_type}")
        
        # Get connection URI
        uri = db_uri or settings.connection_uri
        logger.info(f"Using connection URI: {uri}")
        
        # Determine database type, with special handling for HTTP-based DBs like Qdrant
        detected_db_type = db_type
        if not detected_db_type:
            # For HTTP URIs, don't use the scheme as db_type, use settings.DB_TYPE
            parsed_uri = urlparse(uri)
            if parsed_uri.scheme in ['http', 'https']:
                detected_db_type = settings.DB_TYPE
            else:
                detected_db_type = parsed_uri.scheme
                
            if not detected_db_type:
                detected_db_type = settings.DB_TYPE
            
        console.print(f"Testing connection to [bold]{detected_db_type}[/bold] database...")
        
        # Special handling for Qdrant that uses HTTP protocol
        if detected_db_type.lower() == "qdrant" and uri.startswith("http"):
            parsed = urlparse(uri)
            uri = f"qdrant://{parsed.netloc}{parsed.path}"
            console.print(f"Converted URI to: {uri}")
            
        # Use the orchestrator to test connection
        try:
            # Prepare kwargs for specific database types
            kwargs = {}
            
            if detected_db_type.lower() == "qdrant":
                # Add collection name for Qdrant
                kwargs['collection_name'] = settings.QDRANT_COLLECTION
                kwargs['api_key'] = settings.QDRANT_API_KEY
                kwargs['prefer_grpc'] = settings.QDRANT_PREFER_GRPC
                console.print(f"Using Qdrant collection: [bold]{kwargs.get('collection_name', 'Not specified')}[/bold]")
                
            elif detected_db_type.lower() == "mongodb":
                # Extract database name from MongoDB URI
                parsed_uri = urlparse(uri)
                db_name = parsed_uri.path.lstrip('/')
                if db_name:
                    kwargs['db_name'] = db_name
                    console.print(f"Using MongoDB database: [bold]{db_name}[/bold]")
                else:
                    console.print("[yellow]Warning: No database name found in MongoDB URI. Using default.[/yellow]")
                    # Use a default database name if not in the URI
                    kwargs['db_name'] = "admin"
                
            elif detected_db_type.lower() == "ga4":
                # Add GA4 specific parameters if needed
                kwargs['property_id'] = settings.GA4_PROPERTY_ID if hasattr(settings, 'GA4_PROPERTY_ID') else None
                if kwargs['property_id']:
                    console.print(f"Using GA4 property ID: [bold]{kwargs['property_id']}[/bold]")
                else:
                    console.print("[yellow]Warning: No GA4 property ID found in settings.[/yellow]")
            
            elif detected_db_type.lower() == "shopify":
                # Special handling for Shopify - check if credentials exist
                from pathlib import Path
                credentials_file = os.path.join(str(Path.home()), ".data-connector", "shopify_credentials.json")
                
                if not os.path.exists(credentials_file):
                    console.print("[red]❌ No Shopify credentials found[/red]")
                    console.print("\n💡 [bold]To get started with Shopify:[/bold]")
                    console.print("1. Run: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                    console.print("2. Complete the OAuth flow in your browser")
                    console.print("3. Then test the connection again")
                    console.print(f"\nCredentials will be saved to: [dim]{credentials_file}[/dim]")
                    return
                
                try:
                    with open(credentials_file, 'r') as f:
                        credentials = json.load(f)
                    
                    shops = credentials.get('shops', {})
                    if not shops:
                        console.print("[red]❌ No Shopify shops found in credentials[/red]")
                        console.print("\n💡 [bold]To authenticate:[/bold]")
                        console.print("Run: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                        return
                    
                    shop_count = len(shops)
                    console.print(f"Found {shop_count} Shopify shop(s) in credentials")
                    
                    # Show available shops
                    for shop_domain, shop_data in shops.items():
                        shop_name = shop_data.get('shop_info', {}).get('name', shop_domain)
                        console.print(f"  • [cyan]{shop_name}[/cyan] ([dim]{shop_domain}[/dim])")
                    
                except Exception as e:
                    console.print(f"[red]❌ Error reading Shopify credentials: {e}[/red]")
                    console.print("\n💡 [bold]To fix this:[/bold]")
                    console.print("Run: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                    return
            
            # Add db_type to kwargs
            kwargs['db_type'] = detected_db_type
            
            orchestrator = Orchestrator(uri, **kwargs)
            conn_ok = await orchestrator.test_connection()
            
            if conn_ok:
                console.print("[green]Connection successful![/green]")
            else:
                console.print("[red]Connection failed![/red]")
                
                # Provide specific guidance for Shopify
                if detected_db_type.lower() == "shopify":
                    console.print("\n🔧 [bold]Shopify Connection Troubleshooting:[/bold]")
                    console.print("1. Verify your shop domain is correct")
                    console.print("2. Check if your access token is still valid")
                    console.print("3. Re-authenticate: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                    console.print("4. Ensure the Shopify app has the required permissions")
        except Exception as e:
            error_msg = str(e)
            console.print(f"[red]Connection error: {error_msg}[/red]")
            
            # Provide specific guidance for Shopify errors
            if detected_db_type.lower() == "shopify":
                if "credentials file not found" in error_msg.lower():
                    console.print("\n💡 [bold]Shopify Authentication Required:[/bold]")
                    console.print("Run: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                elif "not authenticated" in error_msg.lower():
                    console.print("\n💡 [bold]Shopify Re-authentication Required:[/bold]")
                    console.print("Your credentials may be expired. Re-authenticate with:")
                    console.print("[bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                elif "401" in error_msg or "unauthorized" in error_msg.lower():
                    console.print("\n💡 [bold]Shopify Authorization Error:[/bold]")
                    console.print("Your access token is invalid. Re-authenticate with:")
                    console.print("[bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                else:
                    console.print("\n💡 [bold]General Shopify Troubleshooting:[/bold]")
                    console.print("1. Verify your shop domain is correct")
                    console.print("2. Re-authenticate: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                    console.print("3. Check if the client app is running: [bold]cd client && npm run dev[/bold]")
    
    asyncio.run(run())

@app.command()
def build_index(
    db_uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)"),
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', 'ga4', etc.)")
):
    """Build schema metadata index"""
    async def run():
        settings = Settings()
        
        # If db_type is specified, update the Settings.DB_TYPE
        if db_type:
            settings.DB_TYPE = db_type
        
        # Get connection URI (possibly based on the new DB_TYPE)
        uri = db_uri or settings.connection_uri
        
        # Determine database type, with special handling for HTTP-based DBs like Qdrant
        detected_db_type = db_type
        if not detected_db_type:
            # For HTTP URIs, don't use the scheme as db_type, use settings.DB_TYPE
            parsed_uri = urlparse(uri)
            if parsed_uri.scheme in ['http', 'https']:
                detected_db_type = settings.DB_TYPE
            else:
                detected_db_type = parsed_uri.scheme
                
            if not detected_db_type:
                detected_db_type = settings.DB_TYPE  # Use the setting
        
        console.print(f"Building schema metadata index for [bold]{detected_db_type}[/bold]...")
        
        # Additional parameters for MongoDB
        kwargs = {}
        if detected_db_type.lower() == "mongodb":
            # Extract database name from MongoDB URI
            parsed_uri = urlparse(uri)
            db_name = parsed_uri.path.lstrip('/')
            if db_name:
                kwargs['db_name'] = db_name
                console.print(f"Using MongoDB database: [bold]{db_name}[/bold]")
            else:
                console.print("[yellow]Warning: No database name found in MongoDB URI. Using default.[/yellow]")
                # Use a default database name if not in the URI
                kwargs['db_name'] = "dataconnector_mongo"
        
        if await ensure_index_exists(db_type=detected_db_type, conn_uri=uri, **kwargs):
            console.print("[green]Index built successfully![/green]")
        else:
            console.print("[red]Failed to build index![/red]")
    
    asyncio.run(run())

@app.command()
def check_schema(
    force: bool = typer.Option(False, "--force", "-f", help="Force reindexing even if no changes detected"),
    db_uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)"),
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', 'ga4', etc.)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Show debug output")
):
    """Check for schema changes and update index if needed"""
    async def run():
        # Set debug logging if requested
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            for handler in logging.getLogger().handlers:
                handler.setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        
        settings = Settings()
        
        # Debug: Print initial DB_TYPE
        console.print(f"[dim]Initial DB_TYPE: {settings.DB_TYPE}[/dim]")
        
        # If db_type is specified, update the Settings.DB_TYPE
        if db_type:
            settings.DB_TYPE = db_type
            console.print(f"[dim]Updated DB_TYPE to: {settings.DB_TYPE}[/dim]")
        
        # Get connection URI (possibly based on the new DB_TYPE)
        uri = db_uri or settings.connection_uri
        
        # Debug: Print connection URI
        console.print(f"[dim]Using connection URI: {uri}[/dim]")
        
        # Determine database type, with special handling for HTTP-based DBs like Qdrant
        detected_db_type = db_type
        if not detected_db_type:
            # For HTTP URIs, don't use the scheme as db_type, use settings.DB_TYPE
            parsed_uri = urlparse(uri)
            if parsed_uri.scheme in ['http', 'https']:
                detected_db_type = settings.DB_TYPE
            else:
                detected_db_type = parsed_uri.scheme
                
            if not detected_db_type:
                detected_db_type = settings.DB_TYPE  # Use the setting
        
        console.print(f"Checking for schema changes in [bold]{detected_db_type}[/bold] database...")
        
        # Additional parameters for MongoDB
        kwargs = {}
        if detected_db_type.lower() == "mongodb":
            # Extract database name from MongoDB URI
            parsed_uri = urlparse(uri)
            db_name = parsed_uri.path.lstrip('/')
            if db_name:
                kwargs['db_name'] = db_name
                console.print(f"Using MongoDB database: [bold]{db_name}[/bold]")
            else:
                console.print("[yellow]Warning: No database name found in MongoDB URI. Using default.[/yellow]")
                # Use a default database name if not in the URI
                kwargs['db_name'] = "dataconnector_mongo"
        
        updated, message = await ensure_schema_index_updated(force=force, db_type=detected_db_type, conn_uri=uri, **kwargs)
        
        if updated:
            console.print(f"[green]{message}[/green]")
        else:
            console.print(f"[yellow]{message}[/yellow]")
    
    asyncio.run(run())

@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question to translate to a database query"),
    analyze: bool = typer.Option(False, "--analyze", "-a", help="Analyze query results"),
    orchestrate: bool = typer.Option(False, "--orchestrate", "-o", help="Use multi-step orchestrated analysis"),
    db_uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)"),
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', 'ga4', etc.)")
):
    """
    Translate natural language to a database query and execute it
    """
    async def run():
        try:
            settings = Settings()
            
            # If db_type is specified, update the Settings.DB_TYPE
            if db_type:
                settings.DB_TYPE = db_type
            
            # Get connection URI (possibly based on the new DB_TYPE)
            uri = db_uri or settings.connection_uri
            
            # Determine database type, with special handling for HTTP-based DBs like Qdrant
            detected_db_type = db_type
            if not detected_db_type:
                # For HTTP URIs, don't use the scheme as db_type, use settings.DB_TYPE
                parsed_uri = urlparse(uri)
                if parsed_uri.scheme in ['http', 'https']:
                    detected_db_type = settings.DB_TYPE
                else:
                    detected_db_type = parsed_uri.scheme
                    
                if not detected_db_type:
                    detected_db_type = settings.DB_TYPE  # Use the setting
            
            console.print(f"Processing query for [bold]{detected_db_type}[/bold] database...")
            
            # Additional parameters based on database type
            kwargs = {}
            
            if detected_db_type.lower() == "mongodb":
                # Extract database name from MongoDB URI
                parsed_uri = urlparse(uri)
                db_name = parsed_uri.path.lstrip('/')
                if db_name:
                    kwargs['db_name'] = db_name
                    console.print(f"Using MongoDB database: [bold]{db_name}[/bold]")
                else:
                    console.print("[yellow]Warning: No database name found in MongoDB URI. Using default.[/yellow]")
                    # Use a default database name if not in the URI
                    kwargs['db_name'] = "dataconnector_mongo"
            
            elif detected_db_type.lower() == "qdrant":
                # Add collection name for Qdrant
                kwargs['collection_name'] = settings.QDRANT_COLLECTION
                kwargs['api_key'] = settings.QDRANT_API_KEY
                kwargs['prefer_grpc'] = settings.QDRANT_PREFER_GRPC
                console.print(f"Using Qdrant collection: [bold]{kwargs['collection_name']}[/bold]")
            
            elif detected_db_type.lower() == "ga4":
                # For GA4, we need to ensure the URI is in the correct format
                # If using a Postgres URI with GA4 db_type, override it
                if not uri.startswith("ga4://"):
                    # Set DB_TYPE to ga4 to ensure correct URI generation
                    settings.DB_TYPE = "ga4"
                    # Regenerate the URI
                    uri = f"ga4://{settings.GA4_PROPERTY_ID}"
                    console.print(f"Using GA4 URI: [bold]{uri}[/bold]")
                
                # Add GA4 specific parameters
                kwargs['property_id'] = settings.GA4_PROPERTY_ID
                if kwargs['property_id']:
                    console.print(f"Using GA4 property ID: [bold]{kwargs['property_id']}[/bold]")
                else:
                    console.print("[yellow]Warning: No GA4 property ID found in settings.[/yellow]")
            
            # Create orchestrator kwargs and connection kwargs separately
            orchestrator_kwargs = dict(kwargs)
            orchestrator_kwargs['db_type'] = detected_db_type
            
            # Create orchestrator for the specified database
            orchestrator = Orchestrator(uri, **orchestrator_kwargs)
            
            # Test connection
            if not await orchestrator.test_connection():
                console.print("[red]Database connection failed![/red]")
                return
            
            # Ensure index exists without passing db_type twice
            if not await ensure_index_exists(db_type=detected_db_type, conn_uri=uri, **kwargs):
                console.print("[red]Failed to create schema index![/red]")
                return
            
            # Automatically check for schema changes (non-forced, quiet)
            await ensure_schema_index_updated(force=False, db_type=detected_db_type, conn_uri=uri, **kwargs)
            
            # Get LLM client
            llm = get_llm_client()
            
            # Use orchestrated analysis if requested
            if orchestrate:
                await run_orchestrated_analysis(llm, question, orchestrator, detected_db_type)
            else:
                # Traditional approach based on database type
                if detected_db_type.lower() == "postgres" or detected_db_type.lower() == "postgresql":
                    await run_postgres_query(llm, question, analyze, orchestrator, detected_db_type)
                elif detected_db_type.lower() == "mongodb":
                    await run_mongodb_query(llm, question, analyze, orchestrator, detected_db_type)
                elif detected_db_type.lower() == "qdrant":
                    await run_qdrant_query(llm, question, analyze, orchestrator, detected_db_type)
                elif detected_db_type.lower() == "slack":
                    await run_slack_query(llm, question, analyze, orchestrator, detected_db_type)
                elif detected_db_type.lower() == "shopify":
                    await run_shopify_query(llm, question, analyze, orchestrator, detected_db_type)
                elif detected_db_type.lower() == "ga4":
                    await run_ga4_query(llm, question, analyze, orchestrator, detected_db_type)
                else:
                    console.print(f"[red]Unsupported database type: {detected_db_type}[/red]")
        
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            import traceback
            console.print(traceback.format_exc())

    asyncio.run(run())

@app.command()
def shopify_scopes(
    shop: Optional[str] = typer.Option(None, "--shop", help="Shop domain to check scopes for")
):
    """Show Shopify scope information - requested vs granted"""
    async def run():
        try:
            from agent.db.adapters.shopify import ShopifyAdapter
            
            # Initialize adapter
            adapter = ShopifyAdapter("https://ceneca.ai", shop_domain=shop)
            
            if not adapter.access_token:
                console.print("[red]❌ No Shopify credentials found[/red]")
                console.print("\n💡 [bold]To authenticate:[/bold]")
                console.print("Run: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                return
            
            # Get scope information
            scope_info = adapter.get_available_scopes()
            
            console.print(f"\n[bold]Shopify Scope Information for: {adapter.shop_domain}[/bold]")
            console.print("="*60)
            
            # Show granted scopes
            granted_scopes = scope_info['granted']
            console.print(f"\n[bold green]✅ Granted Scopes ({len(granted_scopes)}):[/bold green]")
            if granted_scopes:
                for scope in sorted(granted_scopes):
                    console.print(f"  • [green]{scope}[/green]")
            else:
                console.print("  [dim]None[/dim]")
            
            # Show missing scopes
            missing_scopes = scope_info['missing']
            if missing_scopes:
                console.print(f"\n[bold red]❌ Missing Scopes ({len(missing_scopes)}):[/bold red]")
                for scope in sorted(missing_scopes):
                    console.print(f"  • [red]{scope}[/red]")
                
                console.print(f"\n[yellow]⚠️ {len(missing_scopes)} scopes were requested but not granted by the merchant.[/yellow]")
                console.print("These scopes may be needed for full functionality.")
            else:
                console.print(f"\n[bold green]🎉 All requested scopes have been granted![/bold green]")
            
            # Show all requested scopes
            requested_scopes = scope_info['requested']
            console.print(f"\n[bold blue]📋 All Requested Scopes ({len(requested_scopes)}):[/bold blue]")
            if requested_scopes:
                for scope in sorted(requested_scopes):
                    status = "[green]✅[/green]" if scope in granted_scopes else "[red]❌[/red]"
                    console.print(f"  {status} {scope}")
            else:
                console.print("  [dim]None found in shopify.app.toml[/dim]")
            
            # Show summary
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  • Requested: {len(requested_scopes)} scopes")
            console.print(f"  • Granted: {len(granted_scopes)} scopes")
            console.print(f"  • Missing: {len(missing_scopes)} scopes")
            
            if missing_scopes:
                console.print(f"\n[bold yellow]💡 To request missing scopes:[/bold yellow]")
                console.print("1. Update your Shopify app configuration")
                console.print("2. Re-authenticate: [bold]python -m agent.cmd.query authenticate shopify --shop your-store[/bold]")
                console.print("3. The merchant will need to approve the new scopes")
            
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            import traceback
            console.print(traceback.format_exc())
    
    asyncio.run(run())


async def run_orchestrated_analysis(llm, question: str, orchestrator: Orchestrator, db_type: str):
    """Run a multi-step orchestrated analysis"""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Running orchestrated analysis..."),
        transient=True,
    ) as progress:
        progress_task = progress.add_task("Analyzing...", total=None)
        
        # Start orchestration
        result = await llm.orchestrate_analysis(question, db_type=db_type)
        
        progress.update(progress_task, completed=True)
    
    # Display the results
    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return
    
    # Print analysis
    console.print("\n[bold green]Analysis:[/bold green]")
    console.print(Panel(Markdown(result["analysis"])))
    
    # Print execution details
    console.print(f"\n[dim]Analysis completed in {result.get('steps_taken', 0)} steps[/dim]")
    
    # Print queries executed
    state = result.get("state", {})
    queries = state.get("generated_queries", [])
    
    if queries:
        console.print("\n[bold]Queries executed:[/bold]")
        for i, query in enumerate(queries):
            console.print(f"\n[bold cyan]Query {i+1}:[/bold cyan]")
            if db_type in ["postgresql", "postgres"]:
                console.print(f"[cyan]{query.get('sql', 'No SQL query')}[/cyan]")
            else:
                # Format non-SQL queries as JSON
                query_str = json.dumps(query, indent=2)
                console.print(f"[cyan]{query_str}[/cyan]")
                
            if query.get("description"):
                console.print(f"[dim]{query['description']}[/dim]")

async def run_postgres_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a PostgreSQL query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=10, db_type=db_type)
    
    # Render prompt template for PostgreSQL
    prompt = llm.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=question)
    
    # Generate SQL
    console.print("Generating SQL query...")
    sql = await llm.generate_sql(prompt)
    
    # Sanitize SQL
    validated_sql = sanitize_sql(sql)
    
    # Print SQL
    console.print(f"\n[bold cyan]SQL Query:[/bold cyan]")
    console.print(f"[cyan]{validated_sql}[/cyan]\n")
    
    # Execute query using the orchestrator
    console.print("Executing query...")
    
    try:
        rows = await orchestrator.execute(validated_sql)
        
        # Display results
        if rows:
            display_query_results(rows)
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(rows)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(analysis)
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error executing query: {str(e)}[/red]")

async def run_mongodb_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a MongoDB query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
    
    # Get default collection (if applicable)
    default_collection = orchestrator.adapter.default_collection if hasattr(orchestrator.adapter, 'default_collection') else None
    
    # Render prompt template for MongoDB
    prompt = llm.render_template("mongo_query.tpl", 
                              schema_chunks=schema_chunks, 
                              user_question=question,
                              default_collection=default_collection)
    
    # Generate MongoDB query
    console.print("Generating MongoDB query...")
    
    try:
        raw_response = await llm.generate_mongodb_query(prompt)
        
        # Parse response as JSON
        query_data = json.loads(raw_response)
        
        # Print the query
        console.print(f"\n[bold cyan]MongoDB Query:[/bold cyan]")
        formatted_query = json.dumps(query_data, indent=2)
        console.print(f"[cyan]{formatted_query}[/cyan]\n")
        
        # Execute query
        console.print("Executing query...")
        rows = await orchestrator.execute(query_data)
        
        # Display results
        if rows:
            display_query_results(rows)
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(rows)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(analysis)
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error executing query: {str(e)}[/red]")

async def run_qdrant_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a Qdrant vector similarity search query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
    
    # Render prompt template for vector search
    # Note: You'll need to create a vector_search.tpl template
    prompt = llm.render_template("vector_search.tpl", 
                               schema_chunks=schema_chunks, 
                               user_question=question)
    
    console.print("Generating vector search query...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Converting query to vector..."),
        transient=True,
    ) as progress:
        progress_task = progress.add_task("Processing...", total=None)
        
        # Generate Qdrant query
        # This delegates to the adapter's llm_to_query method
        query = await orchestrator.llm_to_query(question, schema_chunks=schema_chunks)
        
        progress.update(progress_task, completed=True)
    
    # Execute query
    console.print("Executing vector search...")
    
    try:
        results = await orchestrator.execute(query)
        
        # Display results
        if results:
            # Format the vector search results in a more readable way
            console.print(f"\n[bold]Found {len(results)} similar items:[/bold]")
            
            # Create table for display
            table = Table(title=f"Vector Search Results ({len(results)} items)")
            
            # Add score column
            table.add_column("Score", style="cyan")
            
            # Add other columns based on the first result
            if results:
                other_cols = [k for k in results[0].keys() if k not in ['score', 'id', 'vector']]
                for col in other_cols[:5]:  # Limit to first 5 columns to avoid table being too wide
                    table.add_column(col.capitalize())
            
            # Add ID column at the end
            table.add_column("ID")
            
            # Add rows (limit to 20 for display)
            display_rows = results[:20]
            for row in display_rows:
                # Format score as percentage
                score = f"{row.get('score', 0) * 100:.2f}%"
                
                # Get other columns
                other_values = []
                for col in other_cols[:5]:
                    val = row.get(col, "")
                    # Truncate long values
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:47] + "..."
                    other_values.append(str(val))
                
                # Add row to table
                table.add_row(score, *other_values, str(row.get('id', '')))
            
            console.print(table)
            
            if len(results) > 20:
                console.print(f"[italic](Showing 20 of {len(results)} results)[/italic]")
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(results, is_vector_search=True)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(Panel(Markdown(analysis)))
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error executing vector search: {str(e)}[/red]")

async def run_slack_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a Slack query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
    
    # Create context from schema chunks
    schema_context = "\n\n".join([chunk.get("content", "") for chunk in schema_chunks])
    
    # Render prompt template for Slack
    prompt = llm.render_template("slack_query.tpl", 
                             schema_context=schema_context, 
                             query=question)
    
    # Generate Slack query
    console.print("Generating Slack query...")
    
    try:
        # Generate query
        response = await llm.generate_mongodb_query(prompt)
        
        # Parse response as JSON
        query_json = None
        
        # Try to extract JSON if embedded in markdown
        if "```json" in response:
            json_text = response.split("```json")[1].split("```")[0].strip()
            query_json = json.loads(json_text)
        else:
            # Otherwise try to parse the whole response
            query_json = json.loads(response)
        
        # Print the query
        console.print(f"\n[bold cyan]Slack Query:[/bold cyan]")
        formatted_query = json.dumps(query_json, indent=2)
        console.print(f"[cyan]{formatted_query}[/cyan]\n")
        
        # Execute query
        console.print("Executing query...")
        results = await orchestrator.execute(query_json)
        
        # Display results
        if results:
            display_query_results(results)
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(results)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(analysis)
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error executing Slack query: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())

async def run_shopify_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a Shopify query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
    
    # Create context from schema chunks
    schema_context = "\n\n".join([chunk.get("content", "") for chunk in schema_chunks])
    
    # Generate Shopify query using the adapter's natural language processing
    console.print("Generating Shopify API query...")
    
    try:
        # Use the adapter's llm_to_query method
        query = await orchestrator.llm_to_query(question, schema_chunks=schema_chunks)
        
        # Print the query
        console.print(f"\n[bold cyan]Shopify Query:[/bold cyan]")
        formatted_query = json.dumps(query, indent=2)
        console.print(f"[cyan]{formatted_query}[/cyan]\n")
        
        # Execute query
        console.print("Executing Shopify API query...")
        results = await orchestrator.execute(query)
        
        # Display results
        if results:
            # Format Shopify results for display
            console.print(f"\n[bold]Retrieved {len(results)} items from Shopify:[/bold]")
            
            # Display in table format
            display_query_results(results)
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(results, is_ecommerce=True)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(Panel(Markdown(analysis)))
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error executing Shopify query: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())

async def run_ga4_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a Google Analytics 4 query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
    
    # Create context from schema chunks
    schema_context = "\n\n".join([chunk.get("content", "") for chunk in schema_chunks])
    
    # Render prompt template for GA4
    prompt = llm.render_template("ga4_query.tpl", 
                             schema_context=schema_context, 
                             query=question)
    
    # Generate GA4 query
    console.print("Generating GA4 query...")
    
    try:
        # Generate query
        response = await llm.generate_mongodb_query(prompt)  # Reusing the MongoDB query generator initially
        
        # Parse response as JSON
        query_json = None
        
        # Try to extract JSON if embedded in markdown
        if "```json" in response:
            json_text = response.split("```json")[1].split("```")[0].strip()
            query_json = json.loads(json_text)
        else:
            # Otherwise try to parse the whole response
            query_json = json.loads(response)
        
        # Print the query
        console.print(f"\n[bold cyan]GA4 Query:[/bold cyan]")
        formatted_query = json.dumps(query_json, indent=2)
        console.print(f"[cyan]{formatted_query}[/cyan]\n")
        
        # Execute query
        console.print("Executing query...")
        results = await orchestrator.execute(query_json)
        
        # Display results
        if results:
            display_query_results(results)
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(results)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(analysis)
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error executing GA4 query: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())

def display_query_results(rows):
    """Display query results in a table"""
    
    # Convert any non-serializable types to strings
    for row in rows:
        for key, value in row.items():
            if not isinstance(value, (str, int, float, bool, type(None))):
                row[key] = str(value)
    
    # Create table for display
    table = Table(title=f"Query Results ({len(rows)} rows)")
    
    # Add columns
    for col in rows[0].keys():
        table.add_column(col)
    
    # Add rows (limit to 20 for display)
    display_rows = rows[:20]
    for row in display_rows:
        table.add_row(*[str(val) for val in row.values()])
    
    console.print(table)
    
    if len(rows) > 20:
        console.print(f"[italic](Showing 20 of {len(rows)} rows)[/italic]")

@app.command()
def search_schema(
    query: str = typer.Argument(..., help="Search query for schema metadata"),
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', etc.)"),
    top_k: int = typer.Option(10, "--limit", "-l", help="Maximum number of results to return")
):
    """
    Search schema metadata
    """
    async def run():
        try:
            settings = Settings()

            # If db_type is specified, update the Settings.DB_TYPE
            if db_type:
                settings.DB_TYPE = db_type 
            
            # Determine database type, with special handling for HTTP-based DBs like Qdrant
            detected_db_type = db_type
            if not detected_db_type:
                # Get URI to check if it's HTTP-based
                uri = settings.connection_uri
                # For HTTP URIs, don't use the scheme as db_type, use settings.DB_TYPE
                parsed_uri = urlparse(uri)
                if parsed_uri.scheme in ['http', 'https']:
                    detected_db_type = settings.DB_TYPE
                else:
                    detected_db_type = parsed_uri.scheme
                    
                if not detected_db_type:
                    detected_db_type = settings.DB_TYPE
            
            # Ensure index exists for this database type
            if not await ensure_index_exists(db_type=detected_db_type):
                console.print("[red]Failed to create schema index![/red]")
                return
            
            console.print(f"Searching [bold]{detected_db_type}[/bold] schema metadata for: [italic]{query}[/italic]")
            
            # Search schema metadata
            searcher = SchemaSearcher(db_type=detected_db_type)
            results = await searcher.search(query, top_k=top_k, db_type=detected_db_type)
            
            # Display results
            console.print(f"\n[bold]Schema Search Results ([green]{len(results)}[/green] found):[/bold]")
            
            for i, result in enumerate(results):
                db_identifier = f"[{result.get('db_type', 'unknown')}]" if 'db_type' in result else ""
                console.print(f"\n[bold cyan]#{i+1}: {result['id']} {db_identifier} (Score: {1.0 - result['distance']:.2f})[/bold cyan]")
                console.print(result['content'])
                console.print("-" * 50)
        
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            import traceback
            console.print(traceback.format_exc())
    
    asyncio.run(run())

@app.command()
def list_sessions(
    limit: int = typer.Option(10, help="Maximum number of sessions to list")
):
    """
    List recent analysis sessions
    """
    async def run():
        state_manager = StateManager()
        sessions = await state_manager.list_sessions(limit=limit)
        
        if not sessions:
            console.print("[yellow]No analysis sessions found[/yellow]")
            return
        
        # Create table for display
        table = Table(title=f"Recent Analysis Sessions")
        table.add_column("Session ID")
        table.add_column("Question")
        table.add_column("Started")
        table.add_column("Status")
        
        for session in sessions:
            # Format the time as a relative time string
            start_time = session.get("start_time", 0)
            now = time.time()
            elapsed = now - start_time
            
            if elapsed < 60:
                time_str = f"{int(elapsed)} seconds ago"
            elif elapsed < 3600:
                time_str = f"{int(elapsed/60)} minutes ago"
            else:
                time_str = f"{int(elapsed/3600)} hours ago"
            
            # Determine status
            has_result = session.get("has_final_result", False)
            status = "[green]Completed[/green]" if has_result else "[yellow]In Progress[/yellow]"
            
            table.add_row(
                session.get("session_id", "Unknown")[:8] + "...",
                session.get("user_question", "Unknown")[:50] + ("..." if len(session.get("user_question", "")) > 50 else ""),
                time_str,
                status
            )
        
        console.print(table)
    
    asyncio.run(run())

@app.command()
def show_session(
    session_id: str = typer.Argument(..., help="Session ID to show details for")
):
    """
    Show details for a specific analysis session
    """
    async def run():
        state_manager = StateManager()
        state = await state_manager.get_state(session_id)
        
        if not state:
            console.print(f"[red]Session {session_id} not found[/red]")
            return
        
        # Display session info
        console.print(Panel(f"[bold]Analysis Session: {session_id}[/bold]"))
        console.print(f"[bold]Question:[/bold] {state.user_question}")
        
        # Show timing info
        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state.start_time))
        console.print(f"[bold]Started:[/bold] {start_time}")
        console.print(f"[bold]Duration:[/bold] {int(time.time() - state.start_time)} seconds")
        
        # Show queries
        if state.generated_queries:
            console.print("\n[bold]Queries:[/bold]")
            for i, query in enumerate(state.generated_queries):
                console.print(f"\n[bold cyan]Query {i+1}:[/bold cyan]")
                console.print(f"[cyan]{query['sql']}[/cyan]")
                if query.get("description"):
                    console.print(f"[dim]{query['description']}[/dim]")
        
        # Show final analysis if available
        if state.final_analysis:
            console.print("\n[bold green]Final Analysis:[/bold green]")
            console.print(Panel(Markdown(state.final_analysis)))
        else:
            console.print("\n[yellow]No final analysis available[/yellow]")
    
    asyncio.run(run())

@app.command()
def cleanup(
    hours: int = typer.Option(24, help="Clean up sessions older than this many hours")
):
    """
    Clean up old analysis sessions
    """
    async def run():
        state_manager = StateManager()
        cleaned = await state_manager.cleanup_old_sessions(max_age_hours=hours)
        console.print(f"[green]Cleaned up {cleaned} old sessions[/green]")
    
    asyncio.run(run())

# Add a new function for managing Slack authentication
async def slack_auth(args):
    """
    Authenticate with Slack using session-based OAuth flow
    """
    # Get MCP URL from config
    config = await load_config_with_defaults()
    mcp_url = config.get("slack", {}).get("mcp_url", "http://localhost:8500")
    print(f"Using MCP server at {mcp_url}")
    
    # Generate a session ID
    session_id = secrets.token_urlsafe(16)
    print(f"Generated session ID: {session_id}")
    
    # Create authorization URL
    auth_url = f"{mcp_url}/api/auth/slack/authorize?session={session_id}"
    
    # Open browser
    print("\n" + "="*60)
    print(f"Opening browser for Slack authentication...")
    print(f"If your browser doesn't open automatically, please visit:")
    print(f"\n{auth_url}\n")
    print("="*60 + "\n")
    
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"Failed to open browser: {e}")
        print(f"Please manually visit the URL above to complete authentication")
    
    # Poll for completion
    print("Waiting for authentication to complete in browser...")
    
    max_attempts = 60  # 5 minutes
    for attempt in range(max_attempts):
        time.sleep(5)  # Poll every 5 seconds
        
        try:
            response = requests.get(f"{mcp_url}/api/auth/slack/check_session/{session_id}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if auth is complete
                if data.get('status') == 'complete':
                    if data.get('success'):
                        print("\nAuthentication successful!")
                        
                        # Save the credentials file
                        user_id = data.get('user_id')
                        workspace_id = data.get('workspace_id')
                        team_name = data.get('team_name', 'Slack Workspace')
                        
                        # Create credentials directory if needed
                        from pathlib import Path
                        
                        credentials_dir = os.path.join(str(Path.home()), ".data-connector")
                        os.makedirs(credentials_dir, exist_ok=True)
                        
                        # Create credentials file
                        credentials = {
                            "user_id": user_id,
                            "workspaces": [
                                {
                                    "id": workspace_id,
                                    "name": team_name,
                                    "is_default": True
                                }
                            ]
                        }
                        
                        credentials_path = os.path.join(credentials_dir, "slack_credentials.json")
                        with open(credentials_path, 'w') as f:
                            json.dump(credentials, f, indent=2)
                            
                        print(f"Credentials saved to {credentials_path}")
                        print(f"\nYou're now authenticated with Slack workspace: {team_name}")
                        print("You can now run slack queries using the data-connector CLI")
                        return True
                    else:
                        print(f"\nAuthentication failed: {data.get('error', 'Unknown error')}")
                        return False
        
        except Exception as e:
            if attempt > 5:
                print(f"Error polling for auth completion: {e}")
    
    print("\nAuthentication timed out after 5 minutes")
    return False

async def slack_list_workspaces(args):
    """
    List all Slack workspaces available to the user
    """
    # Load credentials
    import os
    import json
    from pathlib import Path
    
    credentials_path = os.path.join(str(Path.home()), ".data-connector", "slack_credentials.json")
    
    if not os.path.exists(credentials_path):
        print("No Slack credentials found. Please run 'data-connector slack auth' first.")
        return False
        
    try:
        with open(credentials_path, 'r') as f:
            credentials = json.load(f)
            
        user_id = credentials.get('user_id')
        workspaces = credentials.get('workspaces', [])
        
        if not workspaces:
            print("No workspaces found in credentials file.")
            return False
            
        print("\nAvailable Slack Workspaces:")
        print("="*40)
        
        for i, ws in enumerate(workspaces):
            print(f"{i+1}. {ws.get('name', 'Unknown')} (ID: {ws.get('id')})")
            if ws.get('is_default'):
                print("   DEFAULT")
                
        print("\nTo change the default workspace, edit the credentials file at:")
        print(credentials_path)
            
        return True
    except Exception as e:
        print(f"Error loading workspaces: {e}")
        return False

async def slack_refresh(args):
    """
    Force refresh of Slack schema metadata
    """
    # Get MCP URL from config
    config = await load_config_with_defaults()
    mcp_url = config.get("slack", {}).get("mcp_url", "http://localhost:8500")
    
    # Create orchestrator with Slack adapter
    from agent.db.db_orchestrator import Orchestrator
    print("Refreshing Slack schema...")
    
    try:
        # Initialize orchestrator with Slack adapter
        orchestrator = Orchestrator(mcp_url, db_type="slack")
        
        # Ensure adapter is connected
        if not await orchestrator.adapter.is_connected():
            print("Failed to connect to Slack. Please check your credentials.")
            return False
            
        # Generate schema documents
        schema_docs = await orchestrator.introspect_schema()
        print(f"Generated {len(schema_docs)} schema documents")
        
        # Build and save index
        success = await build_and_save_index_for_db("slack", mcp_url)
        
        if success:
            print("Successfully refreshed Slack schema")
            return True
        else:
            print("Failed to save Slack schema index")
            return False
    except Exception as e:
        print(f"Error refreshing Slack schema: {e}")
        return False
    
async def shopify_auth(args):
    """
    Authenticate with Shopify using OAuth flow with automatic credential polling
    """
    from agent.config.settings import Settings
    from pathlib import Path
    import time
    
    settings = Settings()
    app_url = settings.SHOPIFY_APP_URL
    client_id = settings.SHOPIFY_APP_CLIENT_ID
    
    if not client_id:
        console.print("[red]ERROR: SHOPIFY_APP_CLIENT_ID not configured.[/red]")
        console.print("Please set SHOPIFY_APP_CLIENT_ID in your environment or config file.")
        return False
    
    # Get shop domain from args or prompt user
    shop_domain = args.shop if hasattr(args, 'shop') and args.shop else None
    
    if not shop_domain:
        shop_domain = input("Enter your Shopify shop domain (e.g., mystore.myshopify.com): ").strip()
    
    if not shop_domain:
        console.print("[red]Shop domain is required for authentication.[/red]")
        return False
    
    # Ensure .myshopify.com suffix
    if not shop_domain.endswith('.myshopify.com'):
        if '.' not in shop_domain:
            shop_domain = f"{shop_domain}.myshopify.com"
    
    console.print(f"Authenticating with Shopify shop: [bold]{shop_domain}[/bold]")
    
    # Generate a session ID for tracking this auth flow
    session_id = secrets.token_urlsafe(16)
    console.print(f"Generated session ID: {session_id}")
    
    # Get scopes from TOML file instead of hardcoding them
    from agent.db.adapters.shopify import ShopifyAdapter
    adapter = ShopifyAdapter("https://ceneca.ai")
    scopes = adapter._parse_shopify_app_toml()
    
    console.print(f"[dim]Requesting {len(scopes)} scopes from shopify.app.toml[/dim]")
    
    # Determine environment and redirect URI based on app_url
    redirect_uri = None
    if "localhost" in app_url or "127.0.0.1" in app_url:
        # Development environment
        redirect_uri = f"{app_url}/shopify/callback"
        console.print(f"[dim]Using development environment[/dim]")
    else:
        # Production environment - always use ceneca.ai for production
        redirect_uri = "https://ceneca.ai/shopify/callback"
        console.print(f"[dim]Using production environment[/dim]")
    
    console.print(f"Redirect URI: [dim]{redirect_uri}[/dim]")
    
    # Create Shopify OAuth authorization URL
    from urllib.parse import urlencode
    
    oauth_params = {
        'client_id': client_id,
        'scope': ','.join(scopes),
        'redirect_uri': redirect_uri,
        'state': session_id
    }
    
    auth_url = f"https://{shop_domain}/admin/oauth/authorize?{urlencode(oauth_params)}"
    
    # Set up credentials file path
    credentials_file = os.path.join(str(Path.home()), ".data-connector", "shopify_credentials.json")
    
    def check_credentials_exist():
        """Check if credentials exist for the shop"""
        try:
            console.print(f"[dim]🔍 Checking for credentials file: {credentials_file}[/dim]")
            
            if not os.path.exists(credentials_file):
                console.print(f"[dim]❌ Credentials file does not exist[/dim]")
                return False
            
            console.print(f"[dim]✅ Credentials file exists, reading...[/dim]")
            
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
            
            console.print(f"[dim]📖 Loaded credentials with shops: {list(credentials.get('shops', {}).keys())}[/dim]")
            
            shops = credentials.get('shops', {})
            has_shop = shop_domain in shops
            has_token = shops.get(shop_domain, {}).get('access_token') if has_shop else False
            
            console.print(f"[dim]🔍 Looking for shop: {shop_domain}[/dim]")
            console.print(f"[dim]✅ Has shop: {has_shop}, Has token: {bool(has_token)}[/dim]")
            
            return has_shop and has_token
        except Exception as e:
            console.print(f"[dim]❌ Error checking credentials: {e}[/dim]")
            logger.debug(f"Error checking credentials: {e}")
            return False
    
    # Check if already authenticated
    if check_credentials_exist():
        console.print(f"[green]✅ Already authenticated with {shop_domain}![/green]")
        
        # Test the existing connection
        try:
            from agent.db.adapters.shopify import ShopifyAdapter
            adapter = ShopifyAdapter(app_url, shop_domain=shop_domain)
            if await adapter.test_connection():
                console.print("[green]✅ Connection test successful![/green]")
                console.print("You can run Shopify queries using: [bold]python -m agent.cmd.query --type shopify \"your question\"[/bold]")
                return True
            else:
                console.print("[yellow]⚠️ Existing credentials found but connection test failed. Re-authenticating...[/yellow]")
                # Continue with re-authentication
        except Exception as e:
            console.print(f"[yellow]⚠️ Error testing existing credentials: {e}. Re-authenticating...[/yellow]")
            # Continue with re-authentication
    
    # Start OAuth flow
    console.print("\n" + "="*60)
    console.print(f"Opening browser for Shopify authentication...")
    console.print(f"If your browser doesn't open automatically, please visit:")
    console.print(f"\n{auth_url}\n")
    console.print("="*60 + "\n")
    
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        console.print(f"[red]Failed to open browser: {e}[/red]")
        console.print(f"Please manually visit the URL above to complete authentication")
    
    # Show instructions to user
    console.print("📋 [bold]Complete these steps in your browser:[/bold]")
    console.print("1. Authorize the Ceneca app in Shopify")
    console.print("2. Wait for the success page to appear")
    console.print("3. Return to this terminal\n")
    
    # Poll for credentials to be saved by the OAuth callback
    console.print("🔄 Waiting for OAuth completion...")
    
    max_attempts = 60  # 5 minutes (5 second intervals)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Waiting for authentication..."),
        transient=False,
    ) as progress:
        task = progress.add_task("Authenticating...", total=max_attempts)
        
        for attempt in range(max_attempts):
            await asyncio.sleep(5)  # Check every 5 seconds
            progress.update(task, advance=1)
            
            if check_credentials_exist():
                progress.update(task, completed=max_attempts)
                console.print(f"\n[green]✅ Authentication successful![/green]")
                console.print(f"Credentials saved for shop: [bold]{shop_domain}[/bold]")
                
                # Verify the connection works
                try:
                    from agent.db.adapters.shopify import ShopifyAdapter
                    adapter = ShopifyAdapter(app_url, shop_domain=shop_domain)
                    if await adapter.test_connection():
                        console.print("[green]✅ Connection test successful![/green]")
                        console.print("\n🎉 [bold green]You're all set![/bold green]")
                        console.print("Run Shopify queries using: [bold]python -m agent.cmd.query --type shopify \"your question\"[/bold]")
                        return True
                    else:
                        console.print("[yellow]⚠️ Credentials saved but connection test failed[/yellow]")
                        return False
                except Exception as e:
                    console.print(f"[yellow]⚠️ Credentials saved but connection test failed: {e}[/yellow]")
                    return False
            
            # Show progress every 20 seconds
            if attempt > 0 and attempt % 4 == 0:
                elapsed = (attempt + 1) * 5
                remaining = (max_attempts - attempt - 1) * 5
                console.print(f"[dim]Still waiting... ({elapsed}s elapsed, {remaining}s remaining)[/dim]")
    
    # Timeout
    console.print("\n[red]❌ Authentication timed out after 5 minutes[/red]")
    console.print("\n🔧 [bold]Troubleshooting:[/bold]")
    console.print("1. Make sure the client app is running: [bold]cd client && npm run dev[/bold]")
    console.print("2. Check that your Shopify app redirect URIs include:")
    console.print(f"   • [cyan]{redirect_uri}[/cyan]")
    console.print("3. Ensure you completed the OAuth flow in the browser")
    console.print("4. Check the browser console for any errors")
    console.print(f"5. Verify credentials file location: [dim]{credentials_file}[/dim]")
    
    return False

async def main():
    parser = argparse.ArgumentParser(description='Data Connector CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Create query parser
    query_parser = subparsers.add_parser('query', help='Query a database')
    query_parser.add_argument(
        'query', 
        help='Natural language query to run', 
        nargs='?',
        default=None
    )
    query_parser.add_argument(
        '--type', '-t', 
        choices=['postgres', 'mongodb', 'mongo', 'qdrant', 'slack', 'shopify', 'ga4'], 
        default=None,
        help='Specify database type to query'
    )
    query_parser.add_argument(
        '--complete', '-C', 
        action='store_true', 
        help='Generate complete output'
    )
    query_parser.add_argument(
        '--interactive', '-i', 
        action='store_true', 
        help='Run in interactive mode'
    )
    query_parser.add_argument(
        '--file', '-f', 
        help='File containing the query'
    )
    query_parser.add_argument(
        '--output', '-o', 
        help='Output file to save results'
    )
    
    # Create parser for config commands
    config_parser = subparsers.add_parser('config', help='Configure the Data Connector')
    config_parser.add_argument(
        'config_command', 
        choices=['show', 'set'], 
        help='Config sub-command to run'
    )
    
    # Create parser for auth commands
    auth_parser = subparsers.add_parser('auth', help='Authentication operations')
    auth_parser.add_argument(
        'auth_command',
        choices=['test', 'login', 'logout'],
        default='test',
        nargs='?',
        help='Authentication sub-command to run'
    )
    
    # Create parser for db commands 
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_parser.add_argument(
        'db_command', 
        choices=['list', 'connect', 'test', 'introspect'], 
        help='Database sub-command to run'
    )
    
    # Create parser for slack commands
    slack_parser = subparsers.add_parser('slack', help='Commands for Slack integration')
    slack_subparsers = slack_parser.add_subparsers(dest='slack_command', help='Slack command')
    
    # slack auth
    slack_auth_parser = slack_subparsers.add_parser('auth', help='Authenticate with Slack')
    
    # slack list-workspaces
    slack_list_workspaces_parser = slack_subparsers.add_parser('list-workspaces', help='List available Slack workspaces')
    
    # slack refresh
    slack_refresh_parser = slack_subparsers.add_parser('refresh', help='Force refresh of Slack schema')

    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # Handle different commands
    if args.command == 'query':
        await run_query(args)
    elif args.command == 'config':
        await run_config(args)
    elif args.command == 'db':
        await run_db(args)
    elif args.command == 'auth':
        if args.auth_command == 'test':
            await auth_test()
        elif args.auth_command == 'login':
            await auth_login()
        elif args.auth_command == 'logout':
            console.print("[yellow]Auth logout not yet implemented[/yellow]")
        else:
            auth_parser.print_help()
    # Add support for slack subcommands
    elif args.command == "slack":
        if args.slack_command == "auth":
            await slack_auth(args)
        elif args.slack_command == "list-workspaces":
            await slack_list_workspaces(args)
        elif args.slack_command == "refresh":
            await slack_refresh(args)
        else:
            slack_parser.print_help()

    else:
        parser.print_help()

if __name__ == "__main__":
    # Add command to create __init__.py to make the agent package importable
    def create_init_files():
        """Create __init__.py files in agent directories"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dirs = [
            os.path.join(base_dir, "agent"),
            os.path.join(base_dir, "agent/api"),
            os.path.join(base_dir, "agent/cmd"),
            os.path.join(base_dir, "agent/config"),
            os.path.join(base_dir, "agent/db"),
            os.path.join(base_dir, "agent/llm"),
            os.path.join(base_dir, "agent/meta"),
            os.path.join(base_dir, "agent/prompts"),
            os.path.join(base_dir, "agent/performance"),
            os.path.join(base_dir, "agent/tools")
        ]
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                
            init_file = os.path.join(dir_path, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, "w") as f:
                    pass
    
    create_init_files()
    
    # Try to run with typer app first, fall back to argparse if needed
    try:
        print("Running Typer app...")
        app()
        print("Typer app completed")
    except Exception as e:
        print(f"Typer app failed: {str(e)}. Falling back to argparse.")
        asyncio.run(main())
