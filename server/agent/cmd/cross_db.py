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
from agent.langgraph.integration import LangGraphIntegrationOrchestrator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rich console
console = Console()

# Create typer app
app = typer.Typer(help="Cross-Database Orchestration CLI")

# Global orchestrator instance to avoid re-initialization
_global_orchestrator = None

def get_orchestrator():
    """Get or create the global LangGraph orchestrator instance"""
    global _global_orchestrator
    
    if _global_orchestrator is None:
        config = {
            "use_langgraph_for_complex": True,
            "complexity_threshold": 3,  # Lower threshold for testing
            "preserve_trivial_routing": True,
            "llm_config": {
                "primary_provider": "bedrock",
                "fallbacks": ["anthropic", "openai"]
            }
        }
        _global_orchestrator = LangGraphIntegrationOrchestrator(config)
        console.print("[dim]🔧 Initialized global LangGraph orchestrator[/dim]")
    
    return _global_orchestrator

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

def display_output_breakdown(aggregator):
    """Display comprehensive breakdown of all captured outputs"""
    
    # Get all different types of outputs
    raw_data = aggregator.get_all_raw_data()
    execution_plans = aggregator.get_all_execution_plans()
    tool_executions = aggregator.get_all_tool_executions()
    final_synthesis = aggregator.get_final_synthesis()
    performance = aggregator.get_performance_summary()
    
    # Summary table
    summary_table = Table(title="Output Summary")
    summary_table.add_column("Output Type", style="cyan")
    summary_table.add_column("Count", style="green")
    summary_table.add_column("Description", style="white")
    
    summary_table.add_row("Raw Data Sources", str(len(raw_data)), "Database queries and API responses")
    summary_table.add_row("Execution Plans", str(len(execution_plans)), "Query planning and optimization decisions")
    summary_table.add_row("Tool Executions", str(len(tool_executions)), "Individual tool calls and results")
    summary_table.add_row("Final Synthesis", "1" if final_synthesis else "0", "LLM-generated final response")
    summary_table.add_row("Performance Metrics", "1" if performance else "0", "Timing and resource usage")
    
    console.print(summary_table)
    
    # Raw Data Breakdown
    if raw_data:
        console.print(f"\n[bold yellow]📁 Raw Data Sources ({len(raw_data)})[/bold yellow]")
        data_table = Table()
        data_table.add_column("Source", style="cyan")
        data_table.add_column("Rows", style="green")
        data_table.add_column("Columns", style="yellow")
        data_table.add_column("Execution Time", style="white")
        data_table.add_column("Sample?", style="dim")
        
        total_rows = 0
        for data in raw_data:
            total_rows += data.row_count
            data_table.add_row(
                data.source,
                str(data.row_count),
                str(len(data.columns)),
                f"{data.execution_time_ms:.1f}ms",
                "Yes" if data.is_sample else "No"
            )
        
        console.print(data_table)
        console.print(f"[dim]Total rows retrieved: {total_rows}[/dim]")
    
    # Execution Plans Breakdown
    if execution_plans:
        console.print(f"\n[bold yellow]📋 Execution Plans ({len(execution_plans)})[/bold yellow]")
        for i, plan in enumerate(execution_plans):
            console.print(f"[cyan]Plan {i+1}:[/cyan] {plan.strategy} strategy with {len(plan.operations)} operations")
            if plan.optimizations_applied:
                console.print(f"  Optimizations: {', '.join(plan.optimizations_applied)}")
            if plan.estimated_duration_ms:
                console.print(f"  Estimated duration: {plan.estimated_duration_ms:.1f}ms")
    
    # Tool Executions Breakdown
    if tool_executions:
        console.print(f"\n[bold yellow]🔧 Tool Executions ({len(tool_executions)})[/bold yellow]")
        tool_table = Table()
        tool_table.add_column("Tool ID", style="cyan")
        tool_table.add_column("Status", style="green")
        tool_table.add_column("Execution Time", style="yellow")
        tool_table.add_column("Retries", style="white")
        tool_table.add_column("Dependencies", style="dim")
        
        successful_tools = 0
        total_execution_time = 0
        
        for tool in tool_executions:
            if tool.success:
                successful_tools += 1
                status = "[green]✅ Success[/green]"
            else:
                status = "[red]❌ Failed[/red]"
            
            total_execution_time += tool.execution_time_ms
            
            tool_table.add_row(
                tool.tool_id,
                status,
                f"{tool.execution_time_ms:.1f}ms",
                str(tool.retry_count),
                str(len(tool.dependencies_resolved))
            )
        
        console.print(tool_table)
        console.print(f"[dim]Success rate: {successful_tools}/{len(tool_executions)} ({successful_tools/len(tool_executions)*100:.1f}%)[/dim]")
        console.print(f"[dim]Total tool execution time: {total_execution_time:.1f}ms[/dim]")
    
    # Final Synthesis
    if final_synthesis:
        console.print(f"\n[bold yellow]📝 Final Synthesis[/bold yellow]")
        console.print(f"Response length: {len(final_synthesis.response_text)} characters")
        console.print(f"Confidence score: {final_synthesis.confidence_score:.2f}")
        console.print(f"Sources used: {len(final_synthesis.sources_used)}")
        console.print(f"Synthesis method: {final_synthesis.synthesis_method}")
        
        if final_synthesis.quality_metrics:
            console.print(f"Quality metrics: {final_synthesis.quality_metrics}")
    
    # Performance Summary
    if performance:
        console.print(f"\n[bold yellow]⚡ Performance Metrics[/bold yellow]")
        console.print(f"Total duration: {performance.total_duration_ms:.1f}ms")
        console.print(f"Database query time: {performance.database_query_time:.1f}ms")
        console.print(f"LLM processing time: {performance.llm_processing_time:.1f}ms")
        console.print(f"Operations executed: {performance.operations_executed}")
        console.print(f"Operations successful: {performance.operations_successful}")
        
        if performance.parallel_efficiency:
            console.print(f"Parallel efficiency: {performance.parallel_efficiency:.2f}")
        if performance.cache_hit_rate > 0:
            console.print(f"Cache hit rate: {performance.cache_hit_rate:.2f}")

def display_workflow_timeline(aggregator):
    """Display chronological timeline of workflow execution"""
    
    timeline = aggregator.get_workflow_timeline()
    
    if not timeline:
        console.print("[yellow]No timeline data available[/yellow]")
        return
    
    # Create timeline table
    timeline_table = Table(title="Workflow Execution Timeline")
    timeline_table.add_column("Timestamp", style="dim")
    timeline_table.add_column("Output Type", style="cyan")
    timeline_table.add_column("Node", style="yellow")
    timeline_table.add_column("Summary", style="white")
    timeline_table.add_column("Size", style="green")
    timeline_table.add_column("Duration", style="magenta")
    
    # Parse timeline and add rows
    for event in timeline:
        # Format timestamp (show only time, not date)
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
        except:
            time_str = event["timestamp"][-12:]  # Fallback to last 12 chars
        
        # Format size
        size_bytes = event.get("size_bytes")
        if size_bytes:
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes/1024:.1f}KB"
            else:
                size_str = f"{size_bytes/(1024*1024):.1f}MB"
        else:
            size_str = "-"
        
        # Format processing time
        proc_time = event.get("processing_time_ms")
        time_str_proc = f"{proc_time:.1f}ms" if proc_time else "-"
        
        timeline_table.add_row(
            time_str,
            event["output_type"].replace("_", " ").title(),
            event.get("node_id", "-"),
            event["content_summary"],
            size_str,
            time_str_proc
        )
    
    console.print(timeline_table)
    
    # Show summary statistics
    console.print(f"\n[dim]Timeline contains {len(timeline)} events[/dim]")
    
    # Calculate total data processed
    total_bytes = sum(event.get("size_bytes", 0) for event in timeline)
    if total_bytes > 0:
        if total_bytes < 1024 * 1024:
            console.print(f"[dim]Total data processed: {total_bytes/1024:.1f}KB[/dim]")
        else:
            console.print(f"[dim]Total data processed: {total_bytes/(1024*1024):.1f}MB[/dim]")
    
    # Show event type distribution
    event_types = {}
    for event in timeline:
        event_type = event["output_type"]
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    console.print(f"[dim]Event distribution: {dict(event_types)}[/dim]")

@app.command()
def langgraph(
    question: str = typer.Argument(..., help="Natural language question to execute using LangGraph orchestration"),
    force_langgraph: bool = typer.Option(False, "--force", "-f", help="Force use of LangGraph (bypass complexity analysis)"),
    show_routing: bool = typer.Option(False, "--show-routing", "-r", help="Show routing decision details"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed execution information"),
    show_outputs: bool = typer.Option(False, "--show-outputs", "-o", help="Show comprehensive output breakdown"),
    show_timeline: bool = typer.Option(False, "--show-timeline", "-t", help="Show workflow execution timeline"),
    export_analysis: Optional[str] = typer.Option(None, "--export", "-e", help="Export full analysis to JSON file"),
    save_session: bool = typer.Option(True, "--save-session/--no-save", help="Save session to disk"),
    stream_output: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming output")
):
    """Execute a query using LangGraph orchestration with automatic database detection"""
    async def run():
        # Initialize LangGraph integration orchestrator
        orchestrator = get_orchestrator()
        
        # Create session for tracking
        session_id = str(uuid.uuid4())
        
        console.print(f"🚀 [bold blue]LangGraph Query Execution[/bold blue]")
        console.print(f"Question: [italic]{question}[/italic]")
        console.print(f"Session ID: [dim]{session_id[:8]}...[/dim]")
        console.print()
        
        try:
            # Execute query with LangGraph orchestration
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Processing with LangGraph orchestration..."),
                transient=not verbose,
            ) as progress:
                task = progress.add_task("Executing...", total=None)
                
                # Process query - let LangGraph determine optimal routing and databases
                result = await orchestrator.process_query(
                    question=question,
                    session_id=session_id,
                    databases_available=None,  # Let it auto-detect
                    force_langgraph=force_langgraph
                )
                
                progress.update(task, completed=True)
            
            # CRITICAL: Extract the actual session ID used by the workflow execution
            # The workflow may have created internal sessions we need to track
            actual_session_id = result.get("session_id", session_id)
            if actual_session_id != session_id:
                console.print(f"[dim]🔧 Using workflow session ID: {actual_session_id[:8]}...[/dim]")
                session_id = actual_session_id
            
            # Display routing information if requested
            if show_routing or verbose:
                execution_metadata = result.get("execution_metadata", {})
                routing_method = execution_metadata.get("routing_method", "unknown")
                complexity_analysis = execution_metadata.get("complexity_analysis", {})
                
                console.print(f"\n[bold cyan]Routing Decision:[/bold cyan]")
                console.print(f"Method: [green]{routing_method}[/green]")
                console.print(f"Complexity: {complexity_analysis.get('complexity', 'unknown')}")
                console.print(f"Reason: {complexity_analysis.get('reason', 'No reason provided')}")
                console.print(f"Confidence: {complexity_analysis.get('confidence', 'unknown')}")
            
            # Display execution results
            if "error" in result:
                console.print(f"\n[bold red]❌ Execution Failed[/bold red]")
                console.print(f"Error: {result['error']}")
                
                # Show additional error details if available
                if verbose and "execution_metadata" in result:
                    error_details = result["execution_metadata"].get("error_details")
                    if error_details:
                        console.print(f"Details: {error_details}")
                
                return
            
            # Success - display results based on workflow type
            workflow = result.get("workflow", "unknown")
            console.print(f"\n[bold green]✅ Execution Successful[/bold green] ({workflow} workflow)")
            
            # Display execution summary
            execution_metadata = result.get("execution_metadata", {})
            execution_time = execution_metadata.get("execution_time", 0)
            console.print(f"Execution time: {execution_time:.2f} seconds")
            
            # Show comprehensive output breakdown if requested
            if show_outputs or show_timeline or export_analysis:
                from agent.langgraph.output_aggregator import get_output_integrator
                
                try:
                    output_integrator = get_output_integrator()
                    aggregator = output_integrator.get_aggregator(session_id)
                    
                    # Show output breakdown
                    if show_outputs:
                        console.print(f"\n[bold cyan]📊 Comprehensive Output Analysis[/bold cyan]")
                        display_output_breakdown(aggregator)
                    
                    # Show timeline
                    if show_timeline:
                        console.print(f"\n[bold cyan]⏱️ Workflow Execution Timeline[/bold cyan]")
                        display_workflow_timeline(aggregator)
                    
                    # Export analysis
                    if export_analysis:
                        export_data = aggregator.export_for_analysis()
                        with open(export_analysis, 'w') as f:
                            json.dump(export_data, f, indent=2, default=str)
                        console.print(f"\n[green]📄 Full analysis exported to {export_analysis}[/green]")
                    
                except Exception as e:
                    console.print(f"\n[yellow]⚠️ Could not access output aggregator: {e}[/yellow]")
                    if verbose:
                        import traceback
                        console.print(traceback.format_exc())
            
            # Check for and display visualization data first
            visualization_data = result.get("visualization_data")
            if visualization_data and visualization_data.get("visualization_created"):
                console.print(f"\n[bold green]🎨 Visualization Created[/bold green]")
                chart_type = visualization_data.get("performance_metrics", {}).get("chart_type", "unknown")
                dataset_size = visualization_data.get("dataset_info", {}).get("size", 0)
                console.print(f"Chart type: [cyan]{chart_type}[/cyan]")
                console.print(f"Dataset: [yellow]{dataset_size} rows[/yellow]")
                console.print(f"Intent: [dim]{visualization_data.get('visualization_intent', 'N/A')}[/dim]")
                
                # Show chart configuration summary
                chart_config = visualization_data.get("chart_config", {})
                if chart_config:
                    console.print(f"\n[bold]Chart Configuration:[/bold]")
                    console.print(f"• Type: {chart_config.get('type', 'unknown')}")
                    console.print(f"• Data points: {len(chart_config.get('data', []))}")
                    if 'layout' in chart_config and 'title' in chart_config['layout']:
                        console.print(f"• Title: {chart_config['layout']['title']}")
            
            # Display results based on workflow type
            if workflow == "traditional":
                # Traditional workflow results
                final_result = result.get("final_result", {})
                operation_results = result.get("operation_results", {})
                
                if verbose:
                    console.print(f"\n[bold]Operation Results:[/bold]")
                    for op_id, op_result in operation_results.items():
                        status = "✅" if "error" not in op_result else "❌"
                        console.print(f"{status} {op_id}: {len(op_result.get('data', []))} rows")
                
                # Display final formatted result
                if "formatted_result" in final_result:
                    console.print(f"\n[bold]Results:[/bold]")
                    console.print(Panel(Markdown(final_result["formatted_result"])))
                elif "data" in final_result and final_result["data"]:
                    display_query_results(final_result["data"])
                else:
                    console.print("[yellow]No results to display[/yellow]")
            
            elif workflow == "langgraph":
                # LangGraph workflow results
                node_results = result.get("node_results", {})
                final_state = result.get("final_result", {})
                
                if verbose:
                    console.print(f"\n[bold]Node Execution Results:[/bold]")
                    for node_id, node_result in node_results.items():
                        status = "✅" if "error" not in node_result else "❌"
                        console.print(f"{status} {node_id}")
                
                # Display final results from graph state
                if "operation_results" in final_state:
                    console.print(f"\n[bold]Query Results:[/bold]")
                    operation_results = final_state["operation_results"]
                    
                    # Try to extract and display data
                    all_data = []
                    for op_result in operation_results.values():
                        if isinstance(op_result, dict) and "data" in op_result:
                            all_data.extend(op_result["data"])
                    
                    if all_data:
                        display_query_results(all_data)
                    else:
                        console.print("[yellow]No tabular results to display[/yellow]")
                        # Show raw results if no tabular data
                        if final_state:
                            console.print(f"Final state keys: {list(final_state.keys())}")
                
            elif workflow == "hybrid":
                # Hybrid workflow results
                final_result = result.get("final_result", {})
                operation_results = result.get("operation_results", {})
                hybrid_advantages = result.get("hybrid_advantages", [])
                
                if verbose:
                    console.print(f"\n[bold]Hybrid Workflow Advantages:[/bold]")
                    for advantage in hybrid_advantages:
                        console.print(f"• {advantage}")
                
                # Display results similar to traditional but with hybrid enhancements
                if "formatted_result" in final_result:
                    console.print(f"\n[bold]Results:[/bold]")
                    console.print(Panel(Markdown(final_result["formatted_result"])))
                elif operation_results:
                    # Extract data from operation results
                    all_data = []
                    for op_result in operation_results.values():
                        if isinstance(op_result, dict) and "data" in op_result:
                            all_data.extend(op_result["data"])
                    
                    if all_data:
                        display_query_results(all_data)
                    else:
                        console.print("[yellow]No results to display[/yellow]")
            
            # Show performance statistics if available
            if verbose:
                integration_status = orchestrator.get_integration_status()
                exec_stats = integration_status.get("execution_statistics", {})
                
                console.print(f"\n[bold]LangGraph Integration Statistics:[/bold]")
                console.print(f"Traditional executions: {exec_stats.get('traditional_executions', 0)}")
                console.print(f"LangGraph executions: {exec_stats.get('langgraph_executions', 0)}")
                console.print(f"Hybrid executions: {exec_stats.get('hybrid_executions', 0)}")
            
            # Save session if requested
            if save_session:
                # Use existing state manager to save session details
                state_manager = StateManager()
                session_state = AnalysisState(
                    session_id=session_id,
                    user_question=question
                )
                
                # Add execution metadata as insights
                session_state.add_insight("execution", "LangGraph execution", {
                    "langgraph_execution": True,
                    "workflow_type": workflow,
                    "routing_method": execution_metadata.get("routing_method"),
                    "execution_time": execution_time
                })
                
                # Set final result
                if "final_result" in result:
                    session_state.set_final_result(
                        result["final_result"],
                        result.get("final_result", {}).get("formatted_result", str(result.get("final_result", {})))
                    )
                
                await state_manager.update_state(session_state)
                console.print(f"\n[dim]Session saved with ID: {session_id}[/dim]")
                console.print(f"[dim]Use 'cross_db show-session {session_id}' to view details[/dim]")
        
        except Exception as e:
            console.print(f"\n[bold red]❌ LangGraph Execution Failed[/bold red]")
            console.print(f"Error: {str(e)}")
            
            if verbose:
                import traceback
                console.print(f"\n[dim]Full traceback:[/dim]")
                console.print(traceback.format_exc())
    
    asyncio.run(run())

@app.command("lg")
def langgraph_short(
    question: str = typer.Argument(..., help="Natural language question to execute using LangGraph orchestration"),
    force_langgraph: bool = typer.Option(False, "--force", "-f", help="Force use of LangGraph (bypass complexity analysis)"),
    show_routing: bool = typer.Option(False, "--show-routing", "-r", help="Show routing decision details"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed execution information"),
    show_outputs: bool = typer.Option(False, "--show-outputs", "-o", help="Show comprehensive output breakdown"),
    show_timeline: bool = typer.Option(False, "--show-timeline", "-t", help="Show workflow execution timeline"),
    export_analysis: Optional[str] = typer.Option(None, "--export", "-e", help="Export full analysis to JSON file"),
    save_session: bool = typer.Option(True, "--save-session/--no-save", help="Save session to disk"),
    stream_output: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming output")
):
    """Execute a query using LangGraph orchestration (short alias for 'langgraph')"""
    # Call the main langgraph function with the same parameters
    langgraph(question, force_langgraph, show_routing, verbose, show_outputs, show_timeline, export_analysis, save_session, stream_output)




@app.command(name="bedrock-status")
def bedrock_status():
    """Show Bedrock client singleton status for debugging re-initialization issues"""
    async def run():
        from agent.langgraph.graphs.bedrock_client import get_singleton_status, get_bedrock_langgraph_client
        
        # Get singleton status
        status = get_singleton_status()
        
        console.print("[bold cyan]Bedrock Client Singleton Status[/bold cyan]")
        
        # Create status table
        table = Table(title="Singleton Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Initialized", "[green]Yes[/green]" if status["initialized"] else "[red]No[/red]")
        table.add_row("Config Hash", status.get("config_hash", "None") or "None")
        table.add_row("Is Functional", "[green]Yes[/green]" if status.get("is_functional") else "[red]No[/red]")
        table.add_row("Primary Client", status.get("primary_client", "None") or "None")
        table.add_row("Fallback Count", str(status.get("fallback_count", 0)))
        
        console.print(table)
        
        # Test singleton behavior
        console.print("\n[bold yellow]Testing Singleton Behavior[/bold yellow]")
        
        # Get client twice with same config
        config = {
            "llm_config": {
                "primary_provider": "bedrock",
                "fallbacks": ["anthropic", "openai"]
            }
        }
        
        client1 = get_bedrock_langgraph_client(config)
        client2 = get_bedrock_langgraph_client(config)
        
        if client1 is client2:
            console.print("[green]✅ Singleton working correctly - same instance returned[/green]")
        else:
            console.print("[red]❌ Singleton BROKEN - different instances returned![/red]")
        
        # Show client details
        console.print(f"\nClient 1 ID: {id(client1)}")
        console.print(f"Client 2 ID: {id(client2)}")
        console.print(f"Primary Client: {client1.primary_client}")
        console.print(f"Fallback Clients: {len(client1.fallback_clients)}")
        
        # Show orchestrator status
        console.print("\n[bold yellow]Orchestrator Status[/bold yellow]")
        orchestrator = get_orchestrator()
        console.print(f"Orchestrator ID: {id(orchestrator)}")
        console.print(f"Orchestrator LLM Client ID: {id(orchestrator.llm_client)}")
        console.print(f"Are they the same? {orchestrator.llm_client is client1}")
    
    asyncio.run(run())

if __name__ == "__main__":
    app() 