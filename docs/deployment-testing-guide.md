# Ceneca Deployment Testing Guide

## Overview

This guide provides step-by-step testing procedures for your Ceneca on-premises deployment. It assumes you have your `config.yaml` and `auth-config.yaml` files configured and are using Docker deployment.

## Pre-Deployment Checklist

### 1. Environment Preparation
```bash
# Verify Docker is running
docker --version
docker-compose --version

# Check available disk space (minimum 10GB recommended)
df -h

# Verify your configuration files exist
ls -la ~/.data-connector/
# Should show: config.yaml, auth-config.yaml
```

### 2. Configuration Validation
```bash
# Test your configuration syntax
python -c "import yaml; print(yaml.safe_load(open('~/.data-connector/config.yaml')))"

# Verify your LLM API key is set
grep -o 'api_key: .*' ~/.data-connector/config.yaml
```

## Deployment Testing Scenarios

### Scenario 1: Basic Deployment Test

**Step 1: Clean Deployment**
```bash
# Navigate to your deployment directory
cd ~/ceneca  # or wherever you have your deployment files

# Stop any existing containers
docker-compose down

# Clean up (optional but recommended for testing)
docker system prune -f

# Deploy using your existing script
./deploy.sh
```

**Step 2: Verify Container Health**
```bash
# Check all containers are running
docker ps

# Expected output should show:
# - ceneca-agent (port 8787)
# - postgres (port 6000)
# - Additional services based on your config

# Check logs for any errors
docker logs ceneca-agent
```

**Step 3: Basic Connectivity Test**
```bash
# Test the health endpoint
curl http://localhost:8787/health

# Expected response: {"status": "healthy", "timestamp": "..."}

# Test the main API endpoint
curl http://localhost:8787/api/health
```

### Scenario 2: Database Connection Testing

**Step 1: Test Individual Database Connections**
```bash
# Test PostgreSQL connection
docker exec -it ceneca-agent python -c "
import asyncio
import asyncpg
from agent.config import load_config

async def test_postgres():
    config = load_config()
    try:
        conn = await asyncpg.connect(config['postgres']['uri'])
        result = await conn.fetchval('SELECT 1')
        print(f'PostgreSQL connection: SUCCESS (result: {result})')
        await conn.close()
    except Exception as e:
        print(f'PostgreSQL connection: FAILED - {e}')

asyncio.run(test_postgres())
"

# Test MongoDB connection (if configured)
docker exec -it ceneca-agent python -c "
from pymongo import MongoClient
from agent.config import load_config

config = load_config()
try:
    client = MongoClient(config['mongodb']['uri'])
    client.server_info()
    print('MongoDB connection: SUCCESS')
except Exception as e:
    print(f'MongoDB connection: FAILED - {e}')
"
```

**Step 2: Test Schema Discovery**
```bash
# Test schema introspection
curl -X POST http://localhost:8787/api/agent/schema \
  -H "Content-Type: application/json" \
  -d '{"database_type": "postgres"}'

# Should return schema information about your database
```

### Scenario 3: LLM Integration Testing

**Step 1: Test Trivial LLM (Fast Operations)**
```bash
# Test grammar correction
curl -X POST http://localhost:8787/api/agent/trivial/stream \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "fix_grammar",
    "text": "this are a test sentence with grammar errors"
  }'
```

**Step 2: Test Main LLM Pipeline**
```bash
# Test natural language query
curl -X POST http://localhost:8787/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many records are in my database?",
    "database": "postgres"
  }'
```

**Step 3: Test Cross-Database Query (if multiple DBs configured)**
```bash
# Test cross-database orchestration
curl -X POST http://localhost:8787/api/agent/langgraph/stream \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Compare user counts between PostgreSQL and MongoDB",
    "complexity": 8
  }'
```

### Scenario 4: Authentication Testing (If SSO Enabled)

**Step 1: Test Authentication Endpoints**
```bash
# Test auth health
curl http://localhost:8787/api/agent/auth/health

# Test auth configuration
curl http://localhost:8787/api/agent/auth/config
```

**Step 2: Test SSO Flow**
```bash
# Get login URL
curl -X GET http://localhost:8787/api/agent/auth/login

# This should return a redirect URL to your Okta domain
# Follow the URL in a browser to test the full OAuth flow
```

### Scenario 5: Performance and Load Testing

**Step 1: Concurrent Request Testing**
```bash
# Create a simple load test script
cat > load_test.sh << 'EOF'
#!/bin/bash
for i in {1..10}; do
  curl -X POST http://localhost:8787/api/agent/trivial/stream \
    -H "Content-Type: application/json" \
    -d '{"operation": "improve_text", "text": "This is test number '$i'"}' &
done
wait
EOF

chmod +x load_test.sh
./load_test.sh
```

**Step 2: Memory and CPU Monitoring**
```bash
# Monitor resource usage during testing
docker stats ceneca-agent

# Check logs for any performance warnings
docker logs ceneca-agent --tail 100
```

## Integration Testing with Real Data

### Test 1: End-to-End Query Flow
```bash
# Test complete query flow with your actual data
curl -X POST http://localhost:8787/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the top 5 most recent records in my main table?",
    "database": "postgres",
    "analyze": true
  }'
```

### Test 2: Slack Integration (if configured)
```bash
# Test Slack MCP connection
curl http://localhost:8500/health

# Test Slack OAuth flow
curl -X POST http://localhost:8787/api/agent/slack/auth
```

### Test 3: GA4 Integration (if configured)
```bash
# Test GA4 connection
curl -X POST http://localhost:8787/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was the user count last week?",
    "database": "ga4"
  }'
```

## Troubleshooting Common Issues

### Issue 1: Container Won't Start
```bash
# Check for port conflicts
sudo netstat -tulpn | grep :8787

# Check container logs
docker logs ceneca-agent

# Common fixes:
# 1. Port already in use - change port in config.yaml
# 2. Config file not found - check volume mount
# 3. Database connection failed - verify database URIs
```

### Issue 2: Authentication Failures
```bash
# Check auth configuration
docker exec -it ceneca-agent cat /root/.data-connector/auth-config.yaml

# Test auth endpoints
curl -v http://localhost:8787/api/agent/auth/health

# Common fixes:
# 1. Incorrect Okta configuration
# 2. Network connectivity to Okta
# 3. Missing environment variables
```

### Issue 3: Database Connection Issues
```bash
# Test direct database connection
docker exec -it ceneca-agent python -c "
import asyncio
from agent.db.adapters.postgres import PostgresAdapter
from agent.config import load_config

async def test():
    config = load_config()
    adapter = PostgresAdapter(config['postgres']['uri'])
    await adapter.initialize()
    print('Database connection successful')

asyncio.run(test())
"
```

## Performance Benchmarking

### Benchmark 1: Query Response Time
```bash
# Create benchmark script
cat > benchmark.sh << 'EOF'
#!/bin/bash
echo "Testing query response times..."
for i in {1..5}; do
  echo "Test $i:"
  time curl -X POST http://localhost:8787/api/agent/query \
    -H "Content-Type: application/json" \
    -d '{"question": "Count all records", "database": "postgres"}' \
    > /dev/null 2>&1
done
EOF

chmod +x benchmark.sh
./benchmark.sh
```

### Benchmark 2: Schema Discovery Performance
```bash
# Test schema loading time
time curl -X POST http://localhost:8787/api/agent/schema \
  -H "Content-Type: application/json" \
  -d '{"database_type": "postgres"}'
```

## Production Readiness Checklist

### Security Verification
- [ ] SSL/TLS configured (if using HTTPS)
- [ ] Authentication working correctly
- [ ] No sensitive data in logs
- [ ] Proper firewall rules in place
- [ ] Container security scanning passed

### Performance Verification
- [ ] Response times < 2 seconds for simple queries
- [ ] Memory usage stable under load
- [ ] Database connections properly pooled
- [ ] No memory leaks after extended operation

### Operational Verification
- [ ] Health endpoints responding correctly
- [ ] Logs are properly structured and informative
- [ ] Container restart policies working
- [ ] Backup and recovery procedures tested
- [ ] Monitoring and alerting configured

## Automated Testing Script

Create a comprehensive test script:

```bash
cat > test_deployment.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting Ceneca Deployment Test Suite"
echo "=========================================="

# Test 1: Health Check
echo "Test 1: Health Check"
if curl -f http://localhost:8787/health > /dev/null 2>&1; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi

# Test 2: Database Connection
echo "Test 2: Database Connection"
if curl -f -X POST http://localhost:8787/api/agent/schema \
   -H "Content-Type: application/json" \
   -d '{"database_type": "postgres"}' > /dev/null 2>&1; then
    echo "✅ Database connection passed"
else
    echo "❌ Database connection failed"
    exit 1
fi

# Test 3: LLM Integration
echo "Test 3: LLM Integration"
if curl -f -X POST http://localhost:8787/api/agent/trivial/stream \
   -H "Content-Type: application/json" \
   -d '{"operation": "improve_text", "text": "test"}' > /dev/null 2>&1; then
    echo "✅ LLM integration passed"
else
    echo "❌ LLM integration failed"
    exit 1
fi

# Test 4: Authentication (if enabled)
echo "Test 4: Authentication"
if curl -f http://localhost:8787/api/agent/auth/health > /dev/null 2>&1; then
    echo "✅ Authentication endpoints accessible"
else
    echo "⚠️  Authentication endpoints not accessible (may be disabled)"
fi

echo ""
echo "🎉 All tests passed! Your Ceneca deployment is ready."
echo "Access your deployment at: http://localhost:8787"
EOF

chmod +x test_deployment.sh
./test_deployment.sh
```

## Next Steps After Successful Testing

1. **Document Configuration**: Save your working configuration files
2. **Set Up Monitoring**: Configure log aggregation and monitoring
3. **Create Backup Strategy**: Implement regular backups of configuration
4. **User Training**: Prepare end-user documentation and training
5. **Production Deployment**: Move from testing to production environment

## Support and Debugging

For ongoing support:
- Check container logs: `docker logs ceneca-agent -f`
- Monitor resource usage: `docker stats`
- Review configuration: `docker exec -it ceneca-agent cat /root/.data-connector/config.yaml`
- Test individual components as outlined in this guide

Remember to update your configuration files and restart containers when making changes:
```bash
# After config changes
docker-compose down
./deploy.sh
``` 