#!/usr/bin/env python
"""
Test script for MongoDB adapter.
"""

import asyncio
import os
import sys
import json
import logging
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from agent.db.orchestrator import Orchestrator
from agent.db.adapters.mongo import MongoAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create console for rich output
console = Console()

# Create typer app
app = typer.Typer(help="MongoDB Adapter Tester")

def get_default_mongodb_uri():
    """
    Get MongoDB URI from environment variables or use default Docker Compose values
    """
    username = os.environ.get("MONGO_INITDB_ROOT_USERNAME", "dataconnector")
    password = os.environ.get("MONGO_INITDB_ROOT_PASSWORD", "dataconnector")
    host = os.environ.get("MONGODB_HOST", "localhost")
    port = os.environ.get("MONGODB_PORT", "27000")
    
    return f"mongodb://{username}:{password}@{host}:{port}"

def get_default_db_name():
    """
    Get default database name from environment variables
    """
    return os.environ.get("MONGO_INITDB_DATABASE", "dataconnector_mongo")

@app.command()
def test_connection(
    uri: Optional[str] = typer.Option(None, "--uri", "-u", help="MongoDB connection URI (optional, will use environment settings if not provided)"),
    db_name: Optional[str] = typer.Option(None, "--db", "-d", help="MongoDB database name (optional, will use environment settings if not provided)")
):
    """
    Test connection to MongoDB.
    """
    async def run():
        try:
            # Use provided values or defaults from environment
            actual_uri = uri or get_default_mongodb_uri()
            actual_db = db_name or get_default_db_name()
            
            console.print(f"[bold]Testing connection to MongoDB:[/bold] {actual_uri}")
            console.print(f"[bold]Database:[/bold] {actual_db}")
            
            # Create MongoDB adapter directly
            adapter = MongoAdapter(actual_uri, db_name=actual_db)
            
            # Test connection
            if await adapter.test_connection():
                console.print(Panel("[green bold]Connection successful![/green bold]", 
                                  title="MongoDB Connection Test"))
                
                # List collections
                collection_names = adapter.db.list_collection_names()
                console.print(f"[bold]Collections in {actual_db}:[/bold]")
                for collection in collection_names:
                    console.print(f"  • {collection}")
            else:
                console.print(Panel("[red bold]Connection failed![/red bold]", 
                                  title="MongoDB Connection Test"))
        
        except Exception as e:
            console.print(f"[red bold]Error:[/red bold] {str(e)}")
            import traceback
            console.print(traceback.format_exc())
    
    asyncio.run(run())

@app.command()
def test_query(
    uri: Optional[str] = typer.Option(None, "--uri", "-u", help="MongoDB connection URI (optional, will use environment settings if not provided)"),
    db_name: Optional[str] = typer.Option(None, "--db", "-d", help="MongoDB database name (optional, will use environment settings if not provided)"),
    collection: Optional[str] = typer.Option(None, "--collection", "-c", help="Default collection to query"),
    question: str = typer.Argument(..., help="Natural language question to translate to a MongoDB query")
):
    """
    Test natural language to MongoDB query conversion.
    """
    async def run():
        try:
            # Use provided values or defaults from environment
            actual_uri = uri or get_default_mongodb_uri()
            actual_db = db_name or get_default_db_name()
            
            console.print(f"[bold]Testing MongoDB query generation[/bold]")
            console.print(f"[bold]Database:[/bold] {actual_db}")
            if collection:
                console.print(f"[bold]Default Collection:[/bold] {collection}")
            console.print(f"[bold]Question:[/bold] {question}")
            
            # Create MongoDB adapter directly
            adapter = MongoAdapter(actual_uri, db_name=actual_db, default_collection=collection)
            
            # Generate query
            console.print("\n[bold]Generating MongoDB query...[/bold]")
            query_data = await adapter.llm_to_query(question)
            
            # Print the generated query
            console.print("\n[bold]Generated query:[/bold]")
            
            # Format JSON for display
            formatted_query = json.dumps(query_data, indent=2)
            console.print(Syntax(formatted_query, "json", theme="monokai", line_numbers=True))
            
            # Ask user if they want to execute the query
            execute = typer.confirm("Do you want to execute this query?")
            if execute:
                console.print("\n[bold]Executing query...[/bold]")
                results = await adapter.execute(query_data)
                
                # Print results (limited to 10 rows)
                console.print(f"\n[bold]Query results ([green]{len(results)}[/green] documents):[/bold]")
                if results:
                    if len(results) > 10:
                        preview = json.dumps(results[:10], indent=2)
                        console.print(Syntax(preview, "json", theme="monokai"))
                        console.print(f"[italic](Showing 10 of {len(results)} documents)[/italic]")
                    else:
                        preview = json.dumps(results, indent=2)
                        console.print(Syntax(preview, "json", theme="monokai"))
                else:
                    console.print("[yellow]No results returned[/yellow]")
        
        except Exception as e:
            console.print(f"[red bold]Error:[/red bold] {str(e)}")
            import traceback
            console.print(traceback.format_exc())
    
    asyncio.run(run())

@app.command()
def introspect_schema(
    uri: Optional[str] = typer.Option(None, "--uri", "-u", help="MongoDB connection URI (optional, will use environment settings if not provided)"),
    db_name: Optional[str] = typer.Option(None, "--db", "-d", help="MongoDB database name (optional, will use environment settings if not provided)")
):
    """
    Introspect MongoDB collections and document structures.
    """
    async def run():
        try:
            # Use provided values or defaults from environment
            actual_uri = uri or get_default_mongodb_uri()
            actual_db = db_name or get_default_db_name()
            
            console.print(f"[bold]Introspecting MongoDB schema[/bold]")
            console.print(f"[bold]Database:[/bold] {actual_db}")
            
            # Create MongoDB adapter directly
            adapter = MongoAdapter(actual_uri, db_name=actual_db)
            
            # Introspect schema
            console.print("\n[bold]Introspecting schema...[/bold]")
            schema_documents = await adapter.introspect_schema()
            
            # Print schema documents
            console.print(f"\n[bold]Schema introspection results ([green]{len(schema_documents)}[/green] collections):[/bold]")
            for doc in schema_documents:
                console.print(f"\n[bold cyan]{doc['id']}[/bold cyan]")
                console.print(Panel(doc['content'], title=doc['id'].split(':')[1]))
        
        except Exception as e:
            console.print(f"[red bold]Error:[/red bold] {str(e)}")
            import traceback
            console.print(traceback.format_exc())
    
    asyncio.run(run())

if __name__ == "__main__":
    app() 