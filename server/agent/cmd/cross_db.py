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
from pathlib import Path

print("Starting Cross-Database Orchestration CLI...")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.db.classifier import DatabaseClassifier
from agent.db.registry.integrations import registry_client
from agent.db.orchestrator.cross_db_agent import CrossDatabaseAgent
from agent.db.orchestrator.planning_agent import PlanningAgent
from agent.db.orchestrator.implementation_agent import ImplementationAgent
from agent.db.orchestrator.result_aggregator import ResultAggregator
from agent.db.orchestrator.plans.serialization import serialize_plan, deserialize_plan
from agent.db.orchestrator.plans.dag import OperationDAG
from agent.llm.client import get_llm_client
from agent.tools.state_manager import StateManager, AnalysisState
from agent.config.settings import Settings
from agent.config.config_loader import load_config, load_config_with_defaults

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rich console
console = Console()

# Create typer app
app = typer.Typer(help="Cross-Database Orchestration CLI")

@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question to execute across databases"),
    optimize: bool = typer.Option(False, "--optimize", "-o", help="Optimize the query plan"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Generate plan without executing"),
    show_plan: bool = typer.Option(False, "--show-plan", "-p", help="Show the query plan"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    save_session: bool = typer.Option(True, "--save-session/--no-save", help="Save session to disk")
):
    """Execute a query across multiple databases"""
    async def run():
        # Initialize components
        state_manager = StateManager()
        session_id = await state_manager.create_session(question)
        state = await state_manager.get_state(session_id)
        
        cross_db_agent = CrossDatabaseAgent()
        
        # Add state tracking for this operation
        state.add_executed_tool("cross_db_query", {"question": question, "optimize": optimize}, {})
        
        # Execute the query with progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Running cross-database query..."),
            transient=not verbose,
        ) as progress:
            task = progress.add_task("Analyzing...", total=None)
            
            # Execute the query
            result = await cross_db_agent.execute_query(question, optimize_plan=optimize, dry_run=dry_run)
            
            progress.update(task, completed=True)
        
        # Check if plan generation succeeded
        if "plan" not in result:
            console.print("[red]Failed to generate query plan[/red]")
            console.print(f"Error: {result.get('error', 'Unknown error')}")
            return
        
        # Show the plan if requested
        if show_plan or dry_run or verbose:
            plan = result.get("plan")
            console.print("\n[bold cyan]Query Plan:[/bold cyan]")
            
            # Create a table for the operations
            table = Table(title=f"Plan: {plan.id}")
            table.add_column("Operation ID", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Database", style="yellow")
            table.add_column("Depends On", style="dim")
            
            for op in plan.operations:
                # Get database type if available
                db_type = ""
                if op.source_id:
                    source = registry_client.get_source_by_id(op.source_id)
                    if source:
                        db_type = source.get('type', 'unknown')
                
                # Format dependencies
                depends_on = ", ".join(op.depends_on) if op.depends_on else "None"
                
                # Add row to table
                table.add_row(
                    op.id,
                    op.metadata.get("operation_type", "unknown"),
                    f"{op.source_id or 'N/A'} ({db_type})" if op.source_id else "N/A",
                    depends_on
                )
            
            console.print(table)
        
        # Show validation results if available
        if verbose and "validation" in result:
            validation = result.get("validation", {})
            console.print("\n[bold]Validation Results:[/bold]")
            console.print(f"Valid: [{'green' if validation.get('valid', False) else 'red'}]{validation.get('valid', False)}[/{'green' if validation.get('valid', False) else 'red'}]")
            if validation.get("issues"):
                console.print("Issues:")
                for issue in validation.get("issues", []):
                    console.print(f"- {issue}")
        
        # Show execution results if not a dry run
        if not dry_run:
            # Check execution success
            if result.get("success", False):
                console.print("\n[bold green]Query Execution Successful[/bold green]")
                
                # Show execution summary if verbose
                if verbose and "execution" in result:
                    execution = result.get("execution", {})
                    console.print("\n[bold]Execution Summary:[/bold]")
                    console.print(f"Operations: {execution.get('execution_summary', {}).get('total_operations', 0)}")
                    console.print(f"Successful: {execution.get('execution_summary', {}).get('successful_operations', 0)}")
                    console.print(f"Failed: {execution.get('execution_summary', {}).get('failed_operations', 0)}")
                    console.print(f"Duration: {execution.get('execution_summary', {}).get('execution_time_seconds', 0):.2f} seconds")
                
                # Show results
                if "formatted_result" in result:
                    console.print("\n[bold]Results:[/bold]")
                    console.print(Panel(Markdown(result.get("formatted_result", "No results available"))))
                else:
                    # Fall back to raw results if formatted not available
                    raw_result = result.get("result", {})
                    if isinstance(raw_result, dict) and "data" in raw_result:
                        display_query_results(raw_result.get("data", []))
                    else:
                        console.print("[yellow]No results to display[/yellow]")
            else:
                console.print("\n[bold red]Query Execution Failed[/bold red]")
                console.print(f"Error: {result.get('error', 'Unknown error')}")
                
                # Show more details if available and verbose
                if verbose and "execution" in result:
                    execution = result.get("execution", {})
                    failed_op = execution.get('execution_summary', {}).get('failed_operation_id')
                    if failed_op:
                        console.print(f"Failed operation: {failed_op}")
                        op_details = execution.get('execution_summary', {}).get('operation_details', {}).get(failed_op, {})
                        console.print(f"Error details: {op_details.get('error', 'No details available')}")
        
        # Update state with results
        state.set_final_result(result, result.get("formatted_result", ""))
        
        # Save session if requested
        if save_session:
            await state_manager.update_state(state)
            console.print(f"\n[dim]Session saved with ID: {session_id}[/dim]")
            console.print(f"[dim]Use 'cross_db show-session {session_id}' to view details[/dim]")
        
        return result
    
    asyncio.run(run())

@app.command()
def classify(
    question: str = typer.Argument(..., help="Question to classify for database relevance"),
    threshold: float = typer.Option(0.3, "--threshold", "-t", help="Minimum relevance score (0-1)")
):
    """Determine which databases are relevant for a question"""
    async def run():
        classifier = DatabaseClassifier()
        
        console.print(f"Classifying question: [italic]{question}[/italic]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Analyzing databases..."),
            transient=True,
        ) as progress:
            task = progress.add_task("Classifying...", total=None)
            results = await classifier.classify(question)
            progress.update(task, completed=True)
        
        # Create a table for the results
        table = Table(title="Database Relevance")
        table.add_column("Database", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Relevance", style="green")
        table.add_column("Status", style="bold")
        
        # Get all sources for additional information
        sources = registry_client.get_all_sources()
        sources_by_id = {s["id"]: s for s in sources}
        
        # Get the selected sources from the results
        selected_sources = results.get("sources", [])
        
        # Add rows for each database
        for source in sources:
            db_id = source["id"]
            db_type = source.get("type", "unknown")
            
            # Check if this source was selected
            is_selected = db_id in selected_sources
            
            # Determine relevance based on selection (simple binary for now)
            relevance = 100 if is_selected else 0
            color = "green" if is_selected else "red"
            
            # Determine if this database will be used
            status = "[green]SELECTED[/green]" if is_selected else "[dim]NOT SELECTED[/dim]"
            
            # Add row
            table.add_row(
                db_id,
                db_type,
                f"[{color}]{relevance}%[/{color}]",
                status
            )
        
        # Display reasoning
        reasoning = results.get("reasoning", "No reasoning provided")
        console.print(f"\n[bold]Selection Reasoning:[/bold]")
        console.print(reasoning)
        
        console.print(table)
    
    asyncio.run(run())

@app.command()
def plan(
    question: str = typer.Argument(..., help="Question to generate a query plan for"),
    optimize: bool = typer.Option(False, "--optimize", "-o", help="Optimize the query plan"),
    visualize: bool = typer.Option(False, "--visualize", "-v", help="Create a visual representation of the plan"),
    save_json: Optional[str] = typer.Option(None, "--save", "-s", help="Save plan to JSON file")
):
    """Generate a query plan without executing it"""
    async def run():
        # Initialize the planning agent
        planning_agent = PlanningAgent()
        
        console.print(f"Generating plan for: [italic]{question}[/italic]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Creating query plan..."),
            transient=True,
        ) as progress:
            task = progress.add_task("Planning...", total=None)
            
            # Generate the plan and validate it
            try:
                plan, validation_result = await planning_agent.create_plan(question, optimize=optimize)
            except Exception as e:
                console.print(f"[red]Error generating plan: {str(e)}[/red]")
                return
                
            progress.update(task, completed=True)
        
        # Check if plan generation succeeded
        if not plan or not validation_result.get("valid", False):
            console.print("[red]Failed to generate a valid query plan[/red]")
            if "issues" in validation_result:
                console.print("Issues:")
                for issue in validation_result.get("issues", []):
                    console.print(f"- {issue}")
            return
        
        # Display plan information
        console.print("\n[bold cyan]Query Plan:[/bold cyan]")
        
        # Create a table for the operations
        table = Table(title=f"Plan: {plan.id}")
        table.add_column("Operation ID", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Database", style="yellow")
        table.add_column("Depends On", style="dim")
        
        for op in plan.operations:
            # Get database type if available
            db_type = ""
            if op.source_id:
                source = registry_client.get_source_by_id(op.source_id)
                if source:
                    db_type = source.get('type', 'unknown')
            
            # Format dependencies
            depends_on = ", ".join(op.depends_on) if op.depends_on else "None"
            
            # Add row to table
            table.add_row(
                op.id,
                op.metadata.get("operation_type", "unknown"),
                f"{op.source_id or 'N/A'} ({db_type})" if op.source_id else "N/A",
                depends_on
            )
        
        console.print(table)
        
        # Save plan to JSON if requested
        if save_json:
            plan_json = serialize_plan(plan)
            with open(save_json, 'w') as f:
                json.dump(plan_json, f, indent=2)
            console.print(f"\n[green]Plan saved to {save_json}[/green]")
        
        # Visualize the plan if requested
        if visualize:
            console.print("\n[bold]Plan Visualization:[/bold]")
            console.print("Creating graph representation...")
            
            # Create a DAG from the operations
            dag = OperationDAG(plan)
            
            # Display a simple text-based representation
            for op_id in dag.get_execution_order():
                op = next((o for o in plan.operations if o.id == op_id), None)
                if op:
                    # Get dependencies for indentation
                    deps = op.depends_on
                    indent = "  " * len(deps)
                    console.print(f"{indent}[cyan]{op_id}[/cyan]: {op.metadata.get('operation_type', 'unknown')} on {op.source_id or 'N/A'}")
        
        return plan
    
    asyncio.run(run())

@app.command()
def execute_plan(
    plan_file: str = typer.Argument(..., help="Path to JSON plan file to execute"),
    question: Optional[str] = typer.Option(None, "--question", "-q", help="Original question for context"),
    save_session: bool = typer.Option(True, "--save-session/--no-save", help="Save session to disk")
):
    """Execute a saved query plan"""
    async def run():
        # Load the plan
        try:
            with open(plan_file, 'r') as f:
                plan_json = json.load(f)
            
            plan = deserialize_plan(plan_json)
        except Exception as e:
            console.print(f"[red]Error loading plan: {str(e)}[/red]")
            return
        
        # Create a session if save_session is enabled
        state_manager = None
        state = None
        session_id = None
        
        if save_session:
            state_manager = StateManager()
            user_question = question or f"Executing plan from file: {plan_file}"
            session_id = await state_manager.create_session(user_question)
            state = await state_manager.get_state(session_id)
            
            # Add state tracking for this operation
            state.add_executed_tool("execute_plan", {"plan_file": plan_file, "plan_id": plan.id}, {})
        
        # Create the implementation agent
        implementation_agent = ImplementationAgent()
        
        console.print(f"Executing plan [bold]{plan.id}[/bold] with {len(plan.operations)} operations")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Executing query plan..."),
            transient=True,
        ) as progress:
            task = progress.add_task("Executing...", total=None)
            
            # Execute the plan
            result = await implementation_agent.execute_plan(plan, question or "User query")
            
            progress.update(task, completed=True)
        
        # Display execution summary
        console.print("\n[bold]Execution Summary:[/bold]")
        console.print(f"Total operations: {result['execution_summary']['total_operations']}")
        console.print(f"Successful: {result['execution_summary']['successful_operations']}")
        console.print(f"Failed: {result['execution_summary']['failed_operations']}")
        console.print(f"Duration: {result['execution_summary']['execution_time_seconds']:.2f} seconds")
        
        # Display results
        if result.get("success", False):
            console.print("\n[bold green]Execution succeeded[/bold green]")
            
            # Display the results
            if "result" in result:
                if isinstance(result["result"], dict) and "formatted_result" in result["result"]:
                    console.print("\n[bold]Results:[/bold]")
                    console.print(Panel(Markdown(result["result"]["formatted_result"])))
                elif isinstance(result["result"], dict) and "data" in result["result"]:
                    display_query_results(result["result"]["data"])
                else:
                    console.print(f"\n[bold]Raw Result:[/bold]")
                    console.print(result["result"])
            else:
                console.print("[yellow]No results returned[/yellow]")
        else:
            console.print("\n[bold red]Execution failed[/bold red]")
            console.print(f"Failed operation: {result['execution_summary'].get('failed_operation_id', 'unknown')}")
            
            # Show detailed error if available
            failed_op_id = result['execution_summary'].get('failed_operation_id')
            if failed_op_id and failed_op_id in result['execution_summary'].get('operation_details', {}):
                error = result['execution_summary']['operation_details'][failed_op_id].get('error')
                if error:
                    console.print(f"Error: {error}")
        
        # Update session state if enabled
        if save_session and state:
            # Update state with result
            if "result" in result and isinstance(result["result"], dict) and "formatted_result" in result["result"]:
                state.set_final_result(result, result["result"]["formatted_result"])
            else:
                state.set_final_result(result, str(result.get("result", "No results")))
            
            # Save the updated state
            await state_manager.update_state(state)
            console.print(f"\n[dim]Session saved with ID: {session_id}[/dim]")
            console.print(f"[dim]Use 'cross_db show-session {session_id}' to view details[/dim]")
        
        return result
    
    asyncio.run(run())

@app.command(name="list-sessions")
def list_sessions(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of sessions to show")
):
    """List recent cross-database query sessions"""
    async def run():
        state_manager = StateManager()
        sessions = await state_manager.list_sessions(limit=limit)
        
        if not sessions:
            console.print("[yellow]No analysis sessions found[/yellow]")
            return
        
        # Create table for display
        table = Table(title=f"Recent Analysis Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Question", style="white")
        table.add_column("Started", style="green")
        table.add_column("Status", style="yellow")
        
        for session in sessions:
            # Format the time as a relative time string
            start_time = session.get("start_time", 0)
            now = time.time()
            
            # Ensure start_time is a number
            if isinstance(start_time, str):
                try:
                    start_time = float(start_time)
                except (ValueError, TypeError):
                    start_time = now  # Default to now if conversion fails
            
            try:
                elapsed = now - start_time
            except TypeError:
                elapsed = 0  # Default to 0 if subtraction fails
            
            if elapsed < 60:
                time_str = f"{int(elapsed)} seconds ago"
            elif elapsed < 3600:
                time_str = f"{int(elapsed/60)} minutes ago"
            else:
                time_str = f"{int(elapsed/3600)} hours ago"
            
            # Determine status
            has_result = session.get("has_final_result", False)
            status = "[green]Completed[/green]" if has_result else "[yellow]In Progress[/yellow]"
            
            # Truncate question if needed
            question = session.get("user_question", "Unknown")
            if len(question) > 60:
                question = question[:57] + "..."
            
            table.add_row(
                session.get("session_id", "Unknown")[:8] + "...",
                question,
                time_str,
                status
            )
        
        console.print(table)
    
    asyncio.run(run())

@app.command(name="show-session")
def show_session(
    session_id: str = typer.Argument(..., help="Session ID to display")
):
    """Show details of a specific cross-database query session"""
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
        
        # Show executed tools
        if state.executed_tools:
            console.print("\n[bold]Execution Steps:[/bold]")
            for i, tool in enumerate(state.executed_tools):
                console.print(f"{i+1}. {tool['tool_name']} - {time.strftime('%H:%M:%S', time.localtime(tool['timestamp']))}")
                
                # Show params if available
                if tool.get('params'):
                    params_str = json.dumps(tool['params'], indent=2)
                    if len(params_str) > 100:  # Truncate long params
                        params_str = params_str[:100] + "..."
                    console.print(f"   Params: {params_str}")
        
        # Show queries if available
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
    """Clean up old analysis sessions"""
    async def run():
        state_manager = StateManager()
        cleaned = await state_manager.cleanup_old_sessions(max_age_hours=hours)
        console.print(f"[green]Cleaned up {cleaned} old sessions[/green]")
    
    asyncio.run(run())

@app.command(name="registry-status")
def registry_status():
    """Show status of the schema registry"""
    async def run():
        # Get all sources
        sources = registry_client.get_all_sources()
        
        console.print(f"[bold]Schema Registry Status[/bold]")
        console.print(f"Total registered sources: {len(sources)}")
        
        # Create table for display
        table = Table(title="Registered Data Sources")
        table.add_column("Source ID", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Last Updated", style="yellow")
        table.add_column("Tables/Collections", style="white")
        
        for source in sources:
            # Get table count for this source
            tables = registry_client.list_tables(source["id"])
            
            # Format last updated time
            last_updated = source.get("updated_at", source.get("last_updated", "Never"))
            if isinstance(last_updated, (int, float)):
                # Convert epoch time to relative time
                now = time.time()
                
                # Convert milliseconds to seconds if needed (timestamps over 1 billion likely in milliseconds)
                if last_updated > 1000000000000:  # Timestamp in milliseconds
                    last_updated = last_updated / 1000
                
                elapsed = now - last_updated
                
                if elapsed < 60:
                    last_updated = f"{int(elapsed)} seconds ago"
                elif elapsed < 3600:
                    last_updated = f"{int(elapsed/60)} minutes ago"
                elif elapsed < 86400:
                    last_updated = f"{int(elapsed/3600)} hours ago"
                else:
                    last_updated = f"{int(elapsed/86400)} days ago"
            
            table.add_row(
                source["id"],
                source.get("type", "unknown"),
                last_updated,
                str(len(tables))
            )
        
        console.print(table)
    
    asyncio.run(run())

def display_query_results(rows):
    """Display query results in a table"""
    if not rows:
        console.print("[yellow]No results to display[/yellow]")
        return
        
    # Convert any non-serializable types to strings
    for row in rows:
        for key, value in row.items():
            if not isinstance(value, (str, int, float, bool, type(None))):
                row[key] = str(value)
    
    # Create table for display
    table = Table(title=f"Query Results ({len(rows)} rows)")
    
    # Add columns based on first row
    for col in rows[0].keys():
        table.add_column(col)
    
    # Add rows (limit to 20 for display)
    display_rows = rows[:20]
    for row in display_rows:
        table.add_row(*[str(val) for val in row.values()])
    
    console.print(table)
    
    if len(rows) > 20:
        console.print(f"[italic](Showing 20 of {len(rows)} rows)[/italic]")

if __name__ == "__main__":
    app() 