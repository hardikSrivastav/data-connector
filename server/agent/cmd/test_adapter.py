#!/usr/bin/env python
"""
Test script for database adapters.
"""

import asyncio
import os
import sys
import logging
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from agent.db.db_orchestrator import Orchestrator
from agent.db.adapters.postgres import PostgresAdapter
from agent.config.settings import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create console for rich output
console = Console()

# Create typer app
app = typer.Typer(help="Database Adapter Tester")

@app.command()
def test_connection(
    uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)")
):
    """
    Test database connection using the appropriate adapter.
    """
    async def run():
        try:
            # Get settings
            settings = Settings()
            
            # Use provided URI or default from settings
            conn_uri = uri or settings.connection_uri
            
            console.print(f"[bold]Testing connection to:[/bold] {conn_uri}")
            
            # Create orchestrator with the connection URI
            orchestrator = Orchestrator(conn_uri)
            
            # Test connection
            if await orchestrator.test_connection():
                console.print(Panel("[green bold]Connection successful![/green bold]", 
                                  title="Connection Test"))
            else:
                console.print(Panel("[red bold]Connection failed![/red bold]", 
                                  title="Connection Test"))
                
            # Get adapter info
            adapter_class = orchestrator.adapter.__class__.__name__
            console.print(f"[bold]Using adapter:[/bold] {adapter_class}")
            
        except Exception as e:
            console.print(f"[red bold]Error:[/red bold] {str(e)}")
            
    asyncio.run(run())

@app.command()
def list_adapters():
    """
    List all available database adapters.
    """
    from agent.db.db_orchestrator import ADAPTERS
    
    console.print("[bold]Available Database Adapters:[/bold]")
    
    table = []
    for scheme, adapter_cls in ADAPTERS.items():
        table.append(f"  • [bold cyan]{scheme}:[/bold cyan] {adapter_cls.__name__}")
    
    console.print("\n".join(table))

@app.command()
def test_query(
    question: str = typer.Argument(..., help="Natural language question to translate to a database query"),
    uri: Optional[str] = typer.Option(None, "--uri", "-u", help="Database connection URI (overrides settings)"),
    execute: bool = typer.Option(False, "--execute", "-e", help="Execute the generated query"),
):
    """
    Test natural language to query conversion using the appropriate adapter.
    """
    async def run():
        try:
            # Get settings
            settings = Settings()
            
            # Use provided URI or default from settings
            conn_uri = uri or settings.connection_uri
            
            console.print(f"[bold]Testing query generation for:[/bold] {conn_uri}")
            
            # Create orchestrator with the connection URI
            orchestrator = Orchestrator(conn_uri)
            
            # Generate query
            console.print(f"\n[bold]Generating query for question:[/bold] {question}")
            query = await orchestrator.llm_to_query(question)
            
            # Get adapter info
            adapter_class = orchestrator.adapter.__class__.__name__
            console.print(f"[bold]Using adapter:[/bold] {adapter_class}")
            
            # Print the generated query
            if isinstance(query, str):
                # SQL-like query
                console.print("\n[bold]Generated query:[/bold]")
                console.print(Syntax(query, "sql", theme="monokai", line_numbers=True))
            else:
                # Non-SQL query (e.g. MongoDB pipeline)
                import json
                console.print("\n[bold]Generated query:[/bold]")
                formatted_query = json.dumps(query, indent=2)
                console.print(Syntax(formatted_query, "json", theme="monokai", line_numbers=True))
            
            # Execute if requested
            if execute:
                console.print("\n[bold]Executing query...[/bold]")
                results = await orchestrator.execute(query)
                
                # Print results (limited to 10 rows)
                console.print(f"\n[bold]Query results ([green]{len(results)}[/green] rows):[/bold]")
                if results:
                    if len(results) > 10:
                        console.print(results[:10])
                        console.print(f"[italic](Showing 10 of {len(results)} rows)[/italic]")
                    else:
                        console.print(results)
                else:
                    console.print("[yellow]No results returned[/yellow]")
            
        except Exception as e:
            console.print(f"[red bold]Error:[/red bold] {str(e)}")
            import traceback
            console.print(traceback.format_exc())
            
    asyncio.run(run())

if __name__ == "__main__":
    app() 