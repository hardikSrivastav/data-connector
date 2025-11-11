#!/usr/bin/env python
"""
Test script for the Simple Registry Query Engine

This script tests the simplified query engine that bypasses the plan-execution
mechanism and directly executes queries through adapters.

Usage:
    python test_simple_query_engine.py
    python test_simple_query_engine.py --test single
    python test_simple_query_engine.py --test multi
    python test_simple_query_engine.py --test specific --db-type postgres
"""

import asyncio
import sys
import os
import json
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from server.agent.db.simple_query_engine import SimpleRegistryQueryEngine
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()

async def test_single_database():
    """Test querying a single database"""
    console.print("\n[bold cyan]Test 1: Single Database Query[/bold cyan]")
    console.print("=" * 60)
    
    engine = SimpleRegistryQueryEngine()
    
    # Test with explicit database type
    question = "Show me all customers"
    db_types = ["postgres"]  # Change this to match your setup
    
    console.print(f"Question: [bold]{question}[/bold]")
    console.print(f"Target DB: [bold]{db_types[0]}[/bold]\n")
    
    result = await engine.execute(
        question=question,
        analyze=False,
        db_types=db_types
    )
    
    print_result(result)

async def test_multi_database():
    """Test querying multiple databases in parallel"""
    console.print("\n[bold cyan]Test 2: Multi-Database Query[/bold cyan]")
    console.print("=" * 60)
    
    engine = SimpleRegistryQueryEngine()
    
    # Let classifier determine which databases to query
    question = "Show me orders and payments"
    
    console.print(f"Question: [bold]{question}[/bold]")
    console.print("(Automatic database classification)\n")
    
    result = await engine.execute(
        question=question,
        analyze=False,
        db_types=None  # Let classifier decide
    )
    
    print_result(result)

async def test_with_analysis():
    """Test with LLM analysis enabled"""
    console.print("\n[bold cyan]Test 3: Query with Analysis[/bold cyan]")
    console.print("=" * 60)
    
    engine = SimpleRegistryQueryEngine()
    
    question = "What are the top selling products?"
    
    console.print(f"Question: [bold]{question}[/bold]")
    console.print("Analysis: [bold green]Enabled[/bold green]\n")
    
    result = await engine.execute(
        question=question,
        analyze=True,
        db_types=None
    )
    
    print_result(result)

async def test_specific_database(db_type: str):
    """Test with a specific database type"""
    console.print(f"\n[bold cyan]Test: Specific Database ({db_type})[/bold cyan]")
    console.print("=" * 60)
    
    engine = SimpleRegistryQueryEngine()
    
    # Database-specific questions
    questions = {
        "postgres": "SELECT * FROM customers LIMIT 5",
        "mongodb": "Show me all documents in the orders collection",
        "shopify": "Show me recent orders",
        "payu": "Show me recent transactions",
        "slack": "Show me recent messages"
    }
    
    question = questions.get(db_type.lower(), "Show me some data")
    
    console.print(f"Question: [bold]{question}[/bold]")
    console.print(f"Target DB: [bold]{db_type}[/bold]\n")
    
    result = await engine.execute(
        question=question,
        analyze=False,
        db_types=[db_type]
    )
    
    print_result(result)

async def test_capabilities():
    """Test getting engine capabilities"""
    console.print("\n[bold cyan]Test: Engine Capabilities[/bold cyan]")
    console.print("=" * 60)
    
    engine = SimpleRegistryQueryEngine()
    capabilities = engine.get_capabilities()
    
    console.print(Panel(json.dumps(capabilities, indent=2), title="Engine Capabilities", style="cyan"))

def print_result(result: dict):
    """Pretty print query results"""
    if result.get('success'):
        console.print(Panel("[bold green]✅ Query Successful[/bold green]", style="green"))
        
        # Show databases queried
        databases = result.get('databases_queried', [])
        console.print(f"\n[bold]Databases Queried:[/bold] {', '.join(databases) if databases else 'None'}")
        
        # Show execution time
        exec_time = result.get('execution_time', 0)
        console.print(f"[bold]Execution Time:[/bold] {exec_time:.2f}s")
        
        # Show results count
        results_data = result.get('results', [])
        console.print(f"[bold]Total Results:[/bold] {len(results_data)} rows")
        
        # Show individual source results
        individual = result.get('individual_results', {})
        if individual:
            console.print("\n[bold]Per-Database Results:[/bold]")
            for source_id, source_result in individual.items():
                success_icon = "✅" if source_result.get('success') else "❌"
                row_count = source_result.get('row_count', 0)
                exec_time = source_result.get('execution_time', 0)
                error = source_result.get('error')
                
                if error:
                    console.print(f"  {success_icon} {source_id}: [red]{error}[/red]")
                else:
                    console.print(f"  {success_icon} {source_id}: {row_count} rows in {exec_time:.2f}s")
        
        # Show sample results
        if results_data:
            console.print("\n[bold]Sample Results:[/bold]")
            
            # Create table with first few results
            if len(results_data) > 0:
                # Get all unique keys from first 5 results
                all_keys = set()
                for row in results_data[:5]:
                    if isinstance(row, dict):
                        all_keys.update(row.keys())
                
                # Remove internal metadata keys for display
                display_keys = sorted([k for k in all_keys if not k.startswith('_')])
                
                if display_keys:
                    table = Table(show_header=True, header_style="bold magenta")
                    for key in display_keys:
                        table.add_column(key)
                    
                    # Add rows (limit to 5 for display)
                    for row in results_data[:5]:
                        if isinstance(row, dict):
                            table.add_row(*[str(row.get(k, ''))[:50] for k in display_keys])
                    
                    console.print(table)
                    
                    if len(results_data) > 5:
                        console.print(f"\n[dim]... and {len(results_data) - 5} more rows[/dim]")
        
        # Show analysis if present
        if result.get('analysis'):
            console.print("\n[bold]Analysis:[/bold]")
            console.print(Panel(result['analysis'], style="cyan"))
    else:
        console.print(Panel("[bold red]❌ Query Failed[/bold red]", style="red"))
        error = result.get('error', 'Unknown error')
        console.print(f"\n[red]Error:[/red] {error}")
    
    console.print()

async def run_all_tests():
    """Run all tests"""
    console.print("[bold yellow]Running Simple Query Engine Tests[/bold yellow]")
    
    try:
        # Test capabilities first
        await test_capabilities()
        
        # Test single database
        await test_single_database()
        
        # Test multi-database
        await test_multi_database()
        
        # Test with analysis
        await test_with_analysis()
        
        console.print("\n[bold green]✅ All tests completed[/bold green]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Test failed:[/bold red] {str(e)}")
        import traceback
        console.print(traceback.format_exc())

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Simple Registry Query Engine")
    parser.add_argument(
        '--test',
        choices=['all', 'single', 'multi', 'analysis', 'specific', 'capabilities'],
        default='all',
        help='Which test to run'
    )
    parser.add_argument(
        '--db-type',
        type=str,
        help='Specific database type to test (for "specific" test)'
    )
    
    args = parser.parse_args()
    
    if args.test == 'all':
        asyncio.run(run_all_tests())
    elif args.test == 'single':
        asyncio.run(test_single_database())
    elif args.test == 'multi':
        asyncio.run(test_multi_database())
    elif args.test == 'analysis':
        asyncio.run(test_with_analysis())
    elif args.test == 'specific':
        if not args.db_type:
            console.print("[red]Error: --db-type required for 'specific' test[/red]")
            sys.exit(1)
        asyncio.run(test_specific_database(args.db_type))
    elif args.test == 'capabilities':
        asyncio.run(test_capabilities())

if __name__ == "__main__":
    main()

