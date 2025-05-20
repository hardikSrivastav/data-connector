#!/usr/bin/env python
import typer
import asyncio
import json
import os
import sys
import time
import uuid
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

@app.command()
def test_connection(
    db_uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)"),
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', 'qdrant', 'ga4', etc.)")
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
            
            orchestrator = Orchestrator(uri, **kwargs)
            conn_ok = await orchestrator.test_connection()
            
            if conn_ok:
                console.print("[green]Connection successful![/green]")
            else:
                console.print("[red]Connection failed![/red]")
        except Exception as e:
            console.print(f"[red]Connection error: {str(e)}[/red]")
    
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
                elif detected_db_type.lower() == "ga4":
                    await run_ga4_query(llm, question, analyze, orchestrator, detected_db_type)
                else:
                    console.print(f"[red]Unsupported database type: {detected_db_type}[/red]")
        
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
        choices=['postgres', 'mongodb', 'mongo', 'qdrant', 'slack', 'ga4'], 
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
    print("Running Typer app...")
    app()
    print("Typer app completed")
