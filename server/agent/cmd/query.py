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

print("Starting Data Connector CLI...")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.db.execute import test_conn
from agent.llm.client import get_llm_client
from agent.meta.ingest import SchemaSearcher, ensure_index_exists
from agent.api.endpoints import sanitize_sql
from agent.tools.tools import DataTools
from agent.tools.state_manager import StateManager
from agent.config.settings import Settings
from agent.performance import ensure_schema_index_updated
from agent.db.orchestrator import Orchestrator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rich console
console = Console()

# Create typer app
app = typer.Typer(help="Data Connector CLI")

@app.command()
def test_connection(
    db_uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)")
):
    """Test database connection"""
    async def run():
        settings = Settings()
        uri = db_uri or settings.connection_uri
        
        # Display the database type
        db_type = urlparse(uri).scheme
        console.print(f"Testing connection to [bold]{db_type}[/bold] database...")
        
        # Use the orchestrator to test connection
        try:
            orchestrator = Orchestrator(uri)
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
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', etc.)")
):
    """Build schema metadata index"""
    async def run():
        settings = Settings()
        
        # If db_type is specified, update the Settings.DB_TYPE
        if db_type:
            settings.DB_TYPE = db_type
        
        # Get connection URI (possibly based on the new DB_TYPE)
        uri = db_uri or settings.connection_uri
        
        # Determine database type (from URI or settings)
        detected_db_type = db_type or urlparse(uri).scheme
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
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', etc.)"),
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
        
        # Determine database type (from URI or settings)
        detected_db_type = db_type or urlparse(uri).scheme
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
    db_type: Optional[str] = typer.Option(None, "--type", "-t", help="Database type ('postgres', 'mongodb', etc.)")
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
            
            # Determine database type (from URI or settings)
            detected_db_type = db_type or urlparse(uri).scheme
            if not detected_db_type:
                detected_db_type = settings.DB_TYPE  # Use the setting
            
            console.print(f"Processing query for [bold]{detected_db_type}[/bold] database...")
            
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
            
            # Create orchestrator for the specified database
            orchestrator = Orchestrator(uri, **kwargs)
            
            # Test connection
            if not await orchestrator.test_connection():
                console.print("[red]Database connection failed![/red]")
                return
            
            # Ensure index exists
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
                # Traditional approach
                await run_traditional_query(llm, question, analyze, orchestrator, detected_db_type)
        
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

async def run_traditional_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, db_type: str):
    """Run a traditional natural language to database query"""
    
    # Search schema metadata specific to this database type
    searcher = SchemaSearcher(db_type=db_type)
    schema_chunks = await searcher.search(question, top_k=5, db_type=db_type)
    
    if db_type in ["postgresql", "postgres"]:
        await run_postgres_query(llm, question, analyze, orchestrator, schema_chunks)
    elif db_type == "mongodb":
        await run_mongodb_query(llm, question, analyze, orchestrator, schema_chunks)
    else:
        console.print(f"[red]Unsupported database type: {db_type}[/red]")
        # To run this function for MongoDB, use the following command in the terminal:
        # python -m server.agent.cmd.query run-traditional-query --question "YOUR_QUESTION" --analyze --db-type mongodb

async def run_postgres_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, schema_chunks: List[Dict]):
    """Run a PostgreSQL query"""
    
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

async def run_mongodb_query(llm, question: str, analyze: bool, orchestrator: Orchestrator, schema_chunks: List[Dict]):
    """Run a MongoDB query"""
    
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
    top_k: int = typer.Option(5, "--limit", "-l", help="Maximum number of results to return")
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
            
            # Determine database type from settings if not specified
            detected_db_type = db_type
            if not detected_db_type:
                detected_db_type = urlparse(settings.connection_uri).scheme
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
