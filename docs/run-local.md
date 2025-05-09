# On-Premises Data Science Agent: Run-Local Guide

This document outlines how to deploy and run the Data Science Agent locally within a company’s network—no client data ever leaves their environment.

---

## 1. Overview

A self-contained agent that:

* Connects to a Postgres database via provided credentials
* Generates and executes SQL queries
* Integrates with an LLM for analysis or natural-language interfaces
* Runs 100% on-premises (Docker or executable)
* Never stores or transmits raw client data to external servers

---

## 2. Prerequisites from User

Before installation, the user must supply:

* **Database Connection Details**:

  * `DB_HOST`: Hostname or IP of the Postgres server
  * `DB_PORT`: TCP port (default: `5432`)
  * `DB_NAME`: Database name
  * `DB_USER`: Username with read (or read/write) permissions
  * `DB_PASS`: Password for the database user
  * `SSL_MODE` (optional): e.g. `require`/`verify-full`

* **LLM Configuration** (choose one):

  * **Local LLM**:

    * `MODEL_PATH`: Filesystem path to the model binary(s)
    * `MODEL_TYPE`: e.g. `llama2`, `gpt4all`
    * `DEVICE`: CPU/GPU
  * **Cloud LLM API**:

    * `LLM_API_URL`: Endpoint (e.g. `https://api.openai.com/v1`)
    * `LLM_API_KEY`: Secret API key or token
    * `LLM_MODEL_NAME`: e.g. `gpt-4`, `gpt-4o`

* **Agent Deployment Settings**:

  * `AGENT_PORT`: Local HTTP port (default: `8080`)
  * `LOG_LEVEL`: `info`/`debug`/`error`
  * `CACHE_PATH` (optional): Directory for any encrypted, transient cache
  * `WIPE_ON_EXIT` (flag): Whether to purge cache/logs on shutdown

* **(Optional) Container Registry Credentials**:

  * `REGISTRY_URL`: e.g. `docker.io` or private ECR
  * `REGISTRY_USER` / `REGISTRY_PASS`

---

## 3. Installation & Deployment

### 3.1 Docker Image

```bash
# Pull latest agent image
docker pull your-org/data-agent:latest

# Run agent with environment variables
docker run -d \
  -e DB_HOST=<host> \
  -e DB_PORT=<port> \
  -e DB_NAME=<db> \
  -e DB_USER=<user> \
  -e DB_PASS=<pass> \
  -e LLM_API_URL=<url> \
  -e LLM_API_KEY=<key> \
  -e AGENT_PORT=8080 \
  -p 8080:8080 \
  --name data-agent \
  your-org/data-agent:latest
```

### 3.2 Executable Binary / Python Package

1. **Download** the executable (`data-agent`) for your OS
2. **Or** install from PyPI:

   ```bash
   pip install data-agent
   ```
3. **Run** with a config file or env vars:

   ```bash
   data-agent \
     --db-host <host> \
     --db-port <port> \
     --db-name <db> \
     --db-user <user> \
     --db-pass <pass> \
     --llm-api-url <url> \
     --llm-api-key <key> \
     --port 8080
   ```

---

## 4. Configuration & Usage

Once running, interact via HTTP or CLI:

* **HTTP API** (JSON):

  ```bash
  curl http://localhost:8080/query \
    -H "Content-Type: application/json" \
    -d '{"question":"Show me last month\'s top 10 customers"}'
  ```

* **CLI**:

  ```bash
  data-agent query "List the 5 highest sales by region"
  ```

The agent will:

1. Introspect schema
2. Build SQL
3. Execute on Postgres
4. Optionally feed results + analysis prompts to the LLM
5. Return results and insights

---

## 5. Security & Maintenance

* **Network Isolation**: Run inside corporate VPC/VPN
* **Local Logs Only**: All logging to local FS; no remote endpoints
* **Cache & State**: Encrypted and wiped via `--wipe-on-exit`
* **Updates**: Pull new Docker images or run `pip install --upgrade`

---

## 6. Required User Inputs Summary

| Category               | Parameter        | Description                                   | Example                   |
| ---------------------- | ---------------- | --------------------------------------------- | ------------------------- |
| **Database**           | `DB_HOST`        | Postgres server host/IP                       | `db.internal.company.com` |
|                        | `DB_PORT`        | Postgres TCP port                             | `5432`                    |
|                        | `DB_NAME`        | Database to connect                           | `sales_db`                |
|                        | `DB_USER`        | DB username                                   | `analytics_user`          |
|                        | `DB_PASS`        | DB password                                   | `s3cr3t!`                 |
|                        | `SSL_MODE`       | SSL requirement (optional)                    | `verify-full`             |
| **LLM (Local)**        | `MODEL_PATH`     | Path to local model binaries                  | `/models/llama2.bin`      |
|                        | `MODEL_TYPE`     | LLM architecture (e.g. llama2, gpt4all)       | `llama2`                  |
|                        | `DEVICE`         | Inference device (cpu/gpu)                    | `gpu`                     |
| **LLM (Cloud)**        | `LLM_API_URL`    | Cloud LLM endpoint                            | `https://api.openai.com`  |
|                        | `LLM_API_KEY`    | API key/token                                 | `sk-…`                    |
|                        | `LLM_MODEL_NAME` | Model to use                                  | `gpt-4`                   |
| **Agent Settings**     | `AGENT_PORT`     | Local HTTP port                               | `8080`                    |
|                        | `LOG_LEVEL`      | Logging verbosity                             | `info`                    |
|                        | `CACHE_PATH`     | Directory for transient cache (optional)      | `/tmp/agent-cache`        |
|                        | `WIPE_ON_EXIT`   | Purge cache/logs on shutdown (`true`/`false`) | `true`                    |
| **Container Registry** | `REGISTRY_URL`   | Docker registry (optional)                    | `docker.io`               |
|                        | `REGISTRY_USER`  | Registry username                             | `agent-ci`                |
|                        | `REGISTRY_PASS`  | Registry password                             | `p@ssw0rd`                |

---

Save this file as `run-local.md` and share with your clients as the complete guide to on-premises deployment.
