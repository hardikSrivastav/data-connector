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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rich console
console = Console()

# Create typer app
app = typer.Typer(help="Data Connector CLI")

@app.command()
def test_connection():
    """Test database connection"""
    async def run():
        conn_ok = await test_conn()
        if conn_ok:
            console.print("[green]Connection successful![/green]")
        else:
            console.print("[red]Connection failed![/red]")
    
    asyncio.run(run())

@app.command()
def build_index():
    """Build schema metadata index"""
    async def run():
        console.print("Building schema metadata index...")
        if await ensure_index_exists():
            console.print("[green]Index built successfully![/green]")
        else:
            console.print("[red]Failed to build index![/red]")
    
    asyncio.run(run())

@app.command()
def check_schema(
    force: bool = typer.Option(False, "--force", "-f", help="Force reindexing even if no changes detected")
):
    """Check for schema changes and update index if needed"""
    async def run():
        console.print("Checking for schema changes...")
        
        updated, message = await ensure_schema_index_updated(force=force)
        
        if updated:
            console.print(f"[green]{message}[/green]")
        else:
            console.print(f"[yellow]{message}[/yellow]")
    
    asyncio.run(run())

@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question to translate to SQL"),
    analyze: bool = typer.Option(False, "--analyze", "-a", help="Analyze query results"),
    orchestrate: bool = typer.Option(False, "--orchestrate", "-o", help="Use multi-step orchestrated analysis")
):
    """
    Translate natural language to SQL and execute query
    """
    async def run():
        try:
            # Test connection
            conn_ok = await test_conn()
            if not conn_ok:
                console.print("[red]Database connection failed![/red]")
                return
            
            # Ensure index exists
            if not await ensure_index_exists():
                console.print("[red]Failed to create schema index![/red]")
                return
            
            # Automatically check for schema changes (non-forced, quiet)
            await ensure_schema_index_updated(force=False)
            
            # Get LLM client
            llm = get_llm_client()
            
            # Use orchestrated analysis if requested
            if orchestrate:
                await run_orchestrated_analysis(llm, question)
            else:
                # Traditional approach
                await run_traditional_query(llm, question, analyze)
        
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

    asyncio.run(run())

async def run_orchestrated_analysis(llm, question: str):
    """Run a multi-step orchestrated analysis"""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Running orchestrated analysis..."),
        transient=True,
    ) as progress:
        progress_task = progress.add_task("Analyzing...", total=None)
        
        # Start orchestration
        result = await llm.orchestrate_analysis(question)
        
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
            console.print(f"[cyan]{query['sql']}[/cyan]")
            if query.get("description"):
                console.print(f"[dim]{query['description']}[/dim]")

async def run_traditional_query(llm, question: str, analyze: bool):
    """Run a traditional NL-to-SQL query"""
    
    # Search schema metadata
    searcher = SchemaSearcher()
    schema_chunks = await searcher.search(question, top_k=5)
    
    # Render prompt template
    prompt = llm.render_template("nl2sql.tpl", schema_chunks=schema_chunks, user_question=question)
    
    # Generate SQL
    console.print("Generating SQL query...")
    sql = await llm.generate_sql(prompt)
    
    # Sanitize SQL
    validated_sql = sanitize_sql(sql)
    
    # Print SQL
    console.print(f"\n[bold cyan]SQL Query:[/bold cyan]")
    console.print(f"[cyan]{validated_sql}[/cyan]\n")
    
    # Execute query
    console.print("Executing query...")
    
    # Import here to avoid circular imports
    from agent.db.execute import create_connection_pool
    
    pool = await create_connection_pool()
    try:
        async with pool.acquire() as conn:
            results = await conn.fetch(validated_sql)
            rows = [dict(row) for row in results]
        
        # Convert any non-serializable types to strings
        for row in rows:
            for key, value in row.items():
                if not isinstance(value, (str, int, float, bool, type(None))):
                    row[key] = str(value)
        
        # Display results
        if rows:
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
            
            # Analyze results if requested
            if analyze:
                console.print("\n[bold]Analyzing results...[/bold]")
                analysis = await llm.analyze_results(rows)
                console.print(f"\n[bold green]Analysis:[/bold green]")
                console.print(analysis)
        else:
            console.print("[yellow]No results found[/yellow]")
    finally:
        await pool.close()

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
def search_schema(
    query: str = typer.Argument(..., help="Search query for schema metadata")
):
    """
    Search schema metadata
    """
    async def run():
        try:
            # Ensure index exists
            if not await ensure_index_exists():
                console.print("[red]Failed to create schema index![/red]")
                return
            
            # Search schema metadata
            searcher = SchemaSearcher()
            results = await searcher.search(query, top_k=5)
            
            # Display results
            console.print(f"\n[bold]Schema Search Results:[/bold]")
            
            for i, result in enumerate(results):
                console.print(f"\n[bold cyan]#{i+1}: {result['id']} (Score: {1.0 - result['distance']:.2f})[/bold cyan]")
                console.print(result['content'])
                console.print("-" * 50)
        
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
    
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
    app()
