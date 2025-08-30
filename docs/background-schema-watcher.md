# Background Schema Watcher

The Ceneca Data Connector now includes a background schema watcher that automatically monitors your databases for schema changes and updates the schema registry accordingly.

## Features

- **Automatic Schema Detection**: Monitors PostgreSQL, MongoDB, Qdrant, and other supported databases
- **Multiple Detection Methods**:
  - PostgreSQL: Uses `LISTEN/NOTIFY` with event triggers
  - MongoDB: Uses Change Streams (requires replica set)
  - Qdrant: Monitors vector collections and configurations
  - Fallback: Fingerprint-based change detection for all databases
- **Configurable Intervals**: Default 30-minute checks, fully customizable
- **Docker Integration**: Runs as a separate service in Docker Compose
- **Production Ready**: Includes systemd service configuration

## Quick Start

### Docker Deployment (Recommended)

The schema watcher is automatically included in the Docker Compose setup:

```bash
# Start all services including schema watcher
docker-compose up -d

# View schema watcher logs
docker logs ceneca-schema-watcher -f

# Check schema watcher status
docker ps | grep schema-watcher
```

### Manual Deployment

```bash
# Run once to check for changes
./scripts/start-schema-watcher.sh
export SCHEMA_WATCHER_ONE_TIME=true && ./scripts/start-schema-watcher.sh

# Run continuously with 30-minute intervals
./scripts/start-schema-watcher.sh

# Run with custom interval (15 minutes)
export SCHEMA_WATCHER_INTERVAL=900 && ./scripts/start-schema-watcher.sh
```

### Python Module

```bash
# Run directly with Python
cd server
python -m agent.db.registry.schema_watcher --interval 1800

# One-time check
python -m agent.db.registry.schema_watcher --one-time
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEMA_WATCHER_INTERVAL` | `3600` | Check interval in seconds |
| `SCHEMA_REGISTRY_PATH` | `agent/db/registry/schema_registry.db` | Registry database path |
| `RUNNING_IN_DOCKER` | `false` | Set to `true` in Docker environment |

### Docker Configuration

The schema watcher service is configured in `docker-compose.yml`:

```yaml
schema-watcher:
  build: 
    context: ./server
    dockerfile: Dockerfile
  environment:
    - SCHEMA_WATCHER_INTERVAL=1800  # 30 minutes
    - RUNNING_IN_DOCKER=true
  restart: unless-stopped
  depends_on:
    - postgres
    - mongodb
    - qdrant
```

## Systemd Service

For production deployments on bare metal:

```bash
# Copy service file
sudo cp deploy/systemd/ceneca-schema-watcher.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ceneca-schema-watcher
sudo systemctl start ceneca-schema-watcher

# Check status
sudo systemctl status ceneca-schema-watcher

# View logs
sudo journalctl -u ceneca-schema-watcher -f
```

## How It Works

1. **Initialization**: On startup, runs initial schema introspection for all configured data sources
2. **Change Detection**: 
   - Sets up database-specific listeners where supported
   - Falls back to periodic fingerprint comparison
   - Calculates SHA256 hashes of schema metadata
3. **Automatic Updates**: When changes are detected, automatically runs introspection for affected sources only
4. **Registry Update**: Updates the schema registry with new metadata

## Monitoring

### Logs

The schema watcher provides detailed logging:

```bash
# Docker logs
docker logs ceneca-schema-watcher -f

# Systemd logs
sudo journalctl -u ceneca-schema-watcher -f

# Manual execution logs
tail -f ~/schema_watcher.log
```

### Health Checks

```bash
# Check if schema watcher is running (Docker)
docker ps | grep schema-watcher

# Check systemd service status
sudo systemctl is-active ceneca-schema-watcher

# Manual health check
python -m agent.db.registry.schema_watcher --one-time
```

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the schema watcher has write access to the registry database
2. **Database Connections**: Verify all database URIs in `~/.data-connector/config.yaml`
3. **Docker Networking**: Ensure the watcher can reach database containers

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python -m agent.db.registry.schema_watcher --one-time
```

### Manual Registry Update

```bash
# Force a complete registry update
python -m agent.db.registry.run_introspection
```

## Integration with Main Server

The main agent server also runs initial schema introspection on startup, ensuring the registry is populated even without the background watcher:

- Startup introspection: Immediate schema discovery when server starts
- Background watcher: Continuous monitoring for changes
- Graceful degradation: Server continues to work even if schema watcher fails

## Performance Impact

- **Minimal overhead**: Only runs introspection when changes are detected
- **Efficient detection**: Uses database-native change notifications where possible
- **Configurable intervals**: Balance between responsiveness and resource usage
- **Isolated process**: Runs in separate container/process, doesn't affect main server

## Best Practices

1. **Interval Selection**: 
   - Development: 5-15 minutes for rapid iteration
   - Production: 30-60 minutes for stability
2. **Monitoring**: Set up alerts for schema watcher failures
3. **Backup**: The schema registry database should be included in backups
4. **Testing**: Run one-time checks after major schema changes
