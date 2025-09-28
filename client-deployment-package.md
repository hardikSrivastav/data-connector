# Ceneca Deployment Guide for Client

## 🎯 **Deployment Overview**

Your Ceneca deployment is now **ready with multi-instance MongoDB support**! The intelligent configuration system automatically detects and handles your three MongoDB databases without any manual setup.

## 📦 **What You'll Receive**

### **Deployment Package Contents:**
```
ceneca-enterprise-deployment/
├── install.sh                    # Automated installation script
├── docker-compose.yml            # Container orchestration
├── config.yaml                   # Your customized configuration
├── .env                          # Environment variables
├── README.md                     # Quick start guide
└── docs/
    ├── troubleshooting.md        # Common issues & solutions
    └── multi-database-usage.md   # How to query multiple databases
```

### **Pre-configured for Your Setup:**
- ✅ **3 MongoDB instances** (main, cmots, backend) auto-detected
- ✅ **OpenAI GPT-4** integration ready
- ✅ **Web interface** on port 8787
- ✅ **Cross-database queries** enabled
- ✅ **Enterprise security** settings applied

## 🚀 **Installation Steps (5 Minutes)**

### **Step 1: Prerequisites Check**
```bash
# Verify Docker is installed
docker --version
docker-compose --version

# Ensure network connectivity to your MongoDB host
ping 172.31.18.152
```

### **Step 2: Deploy Ceneca**
```bash
# Extract deployment package
tar -xzf ceneca-enterprise-deployment.tar.gz
cd ceneca-enterprise-deployment/

# Run automated installer
chmod +x install.sh
./install.sh
```

### **Step 3: Verify Configuration**
The installer will create a `config.yaml` pre-configured for your environment:

```yaml
# Your configuration (already optimized)
default_database: mongodb

mongodb:
  main:
    uri: "mongodb://172.31.18.152:27017/financial_data"
    database: "financial_data"
    pool_size: 10
    connect_timeout_ms: 5000
  
  cmots:
    uri: "mongodb://172.31.18.152:27017/discvr_finance"
    database: "discvr_finance"
    pool_size: 10
    connect_timeout_ms: 5000
    
  backend:
    uri: "mongodb://172.31.18.152:27017/finance_cards"
    database: "finance_cards"
    pool_size: 10
    connect_timeout_ms: 5000

llm:
  provider: "openai"
  model: "gpt-4"
  max_tokens: 2000
  temperature: 0.7
```

### **Step 4: Start Services**
```bash
# Start Ceneca (runs in background)
docker-compose up -d

# Verify services are running
docker-compose ps
```

### **Step 5: Access & Test**
```bash
# Open web interface
open http://localhost:8787

# Or test via command line
docker-compose exec ceneca-agent ceneca query "How many documents are in financial_data?"
```

## 🎯 **Multi-Database Usage Examples**

### **Query Individual Databases:**
```bash
# Query specific database
"Show me users from the financial_data database"
"List recent transactions in finance_cards"
"Get analytics data from discvr_finance"
```

### **Cross-Database Analysis:**
```bash
# Compare across databases
"Compare user counts between financial_data and discvr_finance"

# Join data from multiple sources
"Find users in financial_data who also have transactions in finance_cards"

# Aggregate across all databases
"Show total activity across all three MongoDB databases"
```

### **Database-Specific Queries:**
```bash
# The system automatically routes to the right database
ceneca query --source mongodb_main "User statistics"
ceneca query --source mongodb_cmots "Revenue analysis" 
ceneca query --source mongodb_backend "Card usage patterns"
```

## 🔧 **Configuration Management**

### **Update Database Credentials:**
```bash
# Edit configuration
nano config.yaml

# Restart services
docker-compose restart
```

### **Add New Database Instance:**
```yaml
# Add to config.yaml
mongodb:
  main: { ... }
  cmots: { ... }
  backend: { ... }
  # New instance - automatically detected!
  analytics:
    uri: "mongodb://172.31.18.152:27017/analytics_data"
    database: "analytics_data"
```

### **Monitor System Health:**
```bash
# Check logs
docker-compose logs -f

# View system status
docker-compose exec ceneca-agent ceneca status

# Test database connections
docker-compose exec ceneca-agent ceneca test-connections
```

## 📊 **Architecture Overview**

```
┌─────────────────────────────────────────────────────────────┐
│                    Ceneca Agent                             │
├─────────────────────────────────────────────────────────────┤
│  Intelligent Multi-Instance Parser                         │
│  ├── Auto-detects: mongodb_main                           │
│  ├── Auto-detects: mongodb_cmots                          │
│  └── Auto-detects: mongodb_backend                        │
├─────────────────────────────────────────────────────────────┤
│  Cross-Database Orchestrator                               │
│  ├── Individual database queries                          │
│  ├── Cross-database joins                                 │
│  └── Multi-source aggregation                             │
├─────────────────────────────────────────────────────────────┤
│  Web Interface (Port 8787)                                 │
│  ├── Natural language queries                             │
│  ├── Real-time results                                    │
│  └── Data visualization                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Your MongoDB Host                             │
│               172.31.18.152:27017                          │
├─────────────────────────────────────────────────────────────┤
│  financial_data    │  discvr_finance  │  finance_cards     │
│  (mongodb_main)    │  (mongodb_cmots) │  (mongodb_backend) │
└─────────────────────────────────────────────────────────────┘
```

## 🛡️ **Security & Compliance**

### **Data Security:**
- ✅ **On-premise deployment** - no data leaves your network
- ✅ **Encrypted connections** to MongoDB with SSL/TLS
- ✅ **API key protection** - OpenAI key stored securely
- ✅ **Network isolation** - runs in Docker containers
- ✅ **Access logging** - all queries logged for audit

### **Network Configuration:**
```yaml
# Firewall rules needed
Inbound:  Port 8787 (web interface) - internal network only
Outbound: Port 443 (OpenAI API) - internet access
Outbound: Port 27017 (MongoDB) - to 172.31.18.152
```

## 🚨 **Troubleshooting**

### **Common Issues:**

**MongoDB Connection Failed:**
```bash
# Test connectivity
docker-compose exec ceneca-agent ping 172.31.18.152

# Check MongoDB credentials
docker-compose exec ceneca-agent ceneca test-db mongodb_main
```

**OpenAI API Issues:**
```bash
# Verify API key
docker-compose exec ceneca-agent ceneca test-llm

# Check internet connectivity
docker-compose exec ceneca-agent curl -I https://api.openai.com
```

**Web Interface Not Accessible:**
```bash
# Check if service is running
docker-compose ps

# View logs
docker-compose logs ceneca-agent

# Test port binding
netstat -tulpn | grep 8787
```

### **Support Commands:**
```bash
# Generate diagnostic report
docker-compose exec ceneca-agent ceneca diagnostics

# Export configuration
docker-compose exec ceneca-agent ceneca export-config

# Reset to defaults
docker-compose exec ceneca-agent ceneca reset-config
```

## 📞 **Support & Maintenance**

### **Regular Maintenance:**
```bash
# Update Ceneca (monthly)
docker-compose pull
docker-compose up -d

# Backup configuration
cp config.yaml config.yaml.backup.$(date +%Y%m%d)

# Clean up logs (weekly)
docker-compose exec ceneca-agent ceneca cleanup-logs
```

### **Monitoring & Alerts:**
- **Health Check URL:** `http://localhost:8787/health`
- **Metrics Endpoint:** `http://localhost:8787/metrics`
- **Log Location:** `/var/log/ceneca-agent.log`

### **Getting Help:**
- **Documentation:** Check `docs/` folder in deployment package
- **Logs:** Always include logs when reporting issues
- **Configuration:** Sanitize and include `config.yaml` (remove passwords)

---

## 🎉 **You're Ready!**

Your Ceneca deployment with **multi-instance MongoDB support** is production-ready. The intelligent configuration system handles all the complexity automatically - just ask natural language questions and get insights from all your databases!

**Key Benefits You Get:**
- ✅ **Zero configuration** for multi-database setup
- ✅ **Automatic database detection** and routing
- ✅ **Cross-database queries** out of the box
- ✅ **Enterprise security** and compliance
- ✅ **Scalable architecture** for future databases

**Start querying:** `"Show me a summary of data across all our MongoDB databases"`
