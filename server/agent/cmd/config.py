#!/usr/bin/env python
import typer
import os
import sys
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.config.config_loader import load_config, save_config, DEFAULT_CONFIG_LOCATIONS
from agent.config.settings import Settings

# Set up rich console
console = Console()

# Create typer app
app = typer.Typer(help="Data Connector Configuration Manager")

@app.command()
def view(
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """View the current configuration"""
    # Load config
    config = load_config(config_path)
    
    if not config:
        console.print("[yellow]No configuration found.[/yellow]")
        console.print(f"Searched locations: {', '.join(DEFAULT_CONFIG_LOCATIONS)}")
        return
    
    # Display general settings
    console.print(Panel(f"[bold]Data Connector Configuration[/bold]", expand=False))
    console.print(f"Default database: [green]{config.get('default_database', 'postgres')}[/green]")
    
    # Display database settings
    for db_type in ['postgres', 'mongodb']:
        if db_type in config:
            db_config = config[db_type]
            table = Table(title=f"{db_type.capitalize()} Configuration")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")
            
            for key, value in db_config.items():
                # Mask password
                if key == 'password':
                    value = '********'
                table.add_row(key, str(value))
            
            console.print(table)

@app.command("set-database")
def set_database(
    db_type: str = typer.Argument(..., help="Database type (postgres, mongodb)"),
    host: Optional[str] = typer.Option(None, "--host", help="Database host"),
    port: Optional[int] = typer.Option(None, "--port", help="Database port"),
    database: Optional[str] = typer.Option(None, "--database", "-d", help="Database name"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Database user"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Database password"),
    uri: Optional[str] = typer.Option(None, "--uri", help="Complete database URI (overrides other settings)"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """Set database configuration"""
    # Load existing config
    config = load_config(config_path)
    
    # Initialize database section if it doesn't exist
    if db_type not in config:
        config[db_type] = {}
    
    # Update settings that were provided
    if host:
        config[db_type]['host'] = host
    
    if port:
        config[db_type]['port'] = port
    
    if database:
        config[db_type]['database'] = database
    
    if user:
        config[db_type]['user'] = user
    
    if password:
        config[db_type]['password'] = password
    
    # Generate URI if not provided
    if uri:
        config[db_type]['uri'] = uri
    elif all(key in config[db_type] for key in ['host', 'port', 'database', 'user', 'password']):
        # Generate URI based on settings
        if db_type == 'postgres':
            config[db_type]['uri'] = f"postgresql://{config[db_type]['user']}:{config[db_type]['password']}@{config[db_type]['host']}:{config[db_type]['port']}/{config[db_type]['database']}"
            if 'ssl_mode' in config[db_type]:
                config[db_type]['uri'] += f"?sslmode={config[db_type]['ssl_mode']}"
        elif db_type == 'mongodb':
            config[db_type]['uri'] = f"mongodb://{config[db_type]['user']}:{config[db_type]['password']}@{config[db_type]['host']}:{config[db_type]['port']}/{config[db_type]['database']}?authSource=admin"
    
    # Save config
    if save_config(config, config_path):
        console.print(f"[green]Successfully updated {db_type} configuration.[/green]")
    else:
        console.print(f"[red]Failed to save configuration.[/red]")

@app.command("set-default")
def set_default(
    db_type: str = typer.Argument(..., help="Default database type (postgres, mongodb)"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """Set the default database type"""
    # Load existing config
    config = load_config(config_path)
    
    # Update default database
    config['default_database'] = db_type
    
    # Save config
    if save_config(config, config_path):
        console.print(f"[green]Default database set to {db_type}.[/green]")
    else:
        console.print(f"[red]Failed to save configuration.[/red]")

@app.command()
def init(
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """Initialize a new configuration file with default values"""
    # Create default config
    default_config = {
        'default_database': 'postgres',
        'postgres': {
            'host': 'localhost',
            'port': 5432,
            'database': 'dataconnector',
            'user': 'dataconnector',
            'password': 'dataconnector',
            'ssl_mode': 'disable',
            'uri': 'postgresql://dataconnector:dataconnector@localhost:5432/dataconnector'
        },
        'mongodb': {
            'host': 'localhost',
            'port': 27017,
            'database': 'admin',
            'user': 'dataconnector',
            'password': 'dataconnector',
            'uri': 'mongodb://dataconnector:dataconnector@localhost:27017/admin?authSource=admin'
        }
    }
    
    # Check if config already exists
    path = config_path or DEFAULT_CONFIG_LOCATIONS[0]
    if os.path.exists(path):
        overwrite = typer.confirm(f"Configuration file already exists at {path}. Overwrite?")
        if not overwrite:
            console.print("[yellow]Initialization cancelled.[/yellow]")
            return
    
    # Save config
    if save_config(default_config, path):
        console.print(f"[green]Configuration initialized at {path}[/green]")
        console.print("[bold]Note:[/bold] The file is set to be readable only by the current user for security.")
    else:
        console.print(f"[red]Failed to initialize configuration.[/red]")

if __name__ == "__main__":
    app() 