# Ceneca On-Prem Deployment Blueprint

## Introduction

Ceneca is an **on-premise AI data analyst** that connects directly to your enterprise data sources (databases, APIs, and internal tools). It allows users to ask natural-language questions and get insights from their data without exposing any information outside their security perimeter. This guide provides a full technical deployment blueprint for installing and running Ceneca in an enterprise environment with minimal friction. We will cover setting up the required files and directories, configuring connections in a single YAML file, and deploying the system via Docker (default) or alternatives like Kubernetes or direct execution. We also include sample configuration, Dockerfile(s), an optional Kubernetes manifest, a startup script, and usage examples. The goal is to enable an enterprise user to go from **installation to insight** with as few steps as possible while ensuring all data stays on-prem.

**Key Features Supported:** Ceneca can connect to multiple data sources – **PostgreSQL**, **MongoDB**, **Slack** (as a data source via message history), **Google Analytics 4 (GA4)**, and **Qdrant** (vector database) – all queryable through the same natural language interface. By default it runs as a local web service (HTTP API/UI) on port **8787** (configurable), and includes a CLI for running queries and tests. The only setup required from the user is to provide connection details and credentials in a **`config.yaml`** file; everything else (container orchestration, environment setup) is handled automatically. A placeholder for **license key validation** is included, ready to be extended in future without affecting the deployment steps.

## File & Directory Structure

For a clean installation, we recommend organizing Ceneca’s deployment files in a single folder (e.g., `ceneca/`). Below is a suggested structure of the key files and directories and their purposes:

```
ceneca/                        # Deployment root folder (can be named as needed)
├── config.yaml                # **Primary configuration file** for all connections and settings (only file you edit)
├── deploy.sh                  # **Deployment script** to launch Ceneca (Docker by default)
├── docker-compose.yml         # Docker Compose file defining all required services/containers
├── Dockerfile                 # Dockerfile for the Ceneca agent (core on-prem AI analyst service)
├── Dockerfile.mcp             # Dockerfile for Slack MCP microservice (handles Slack OAuth & data, if Slack is used)
├── k8s/
│   └── ceneca-deployment.yaml # Example Kubernetes manifest to deploy the same services (optional)
└── ... (any additional scripts or docs as needed)
```

**Highlights:**

* **`config.yaml`:** Contains all user-specific configuration (database URIs, API keys, service toggles, etc.). This is the **only file you need to modify** to configure Ceneca for your environment.
* **Deployment Script (`deploy.sh`):** A one-click script to bring up the entire Ceneca stack. By default, it uses Docker Compose to start the services. For example, it may simply call `docker-compose up -d` (detached) to launch all containers. This abstracts away manual Docker commands – the enterprise user just runs `./deploy.sh` and the system comes online.
* **Docker Compose (`docker-compose.yml`):** Describes how each component of Ceneca runs in Docker. It defines the Ceneca agent service, plus auxiliary services for data stores or integrations (e.g., optional internal databases or Slack-related services). Docker is the default deployment method for simplicity, bundling all components into an isolated environment.
* **Docker Images (via Dockerfile(s)):** The core **Ceneca agent** image is built using the provided `Dockerfile` (Python-based). There is also a separate Dockerfile (`Dockerfile.mcp`) for the Slack integration service (sometimes called the “MCP” server) which handles Slack OAuth and data indexing. These images can be built locally or pulled from a registry. By providing Dockerfiles, enterprise users have transparency and can build images on-prem if needed.
* **Kubernetes config (optional):** The `k8s/` directory contains an example manifest for deploying Ceneca on a Kubernetes cluster. This is provided for enterprises that prefer using K8s instead of Docker Compose. It defines Kubernetes **Deployments** for the Ceneca agent and supporting services, along with Services (for networking) and PersistentVolumeClaims (for any data persistence). This manifest can be applied with a single `kubectl apply -f ceneca-deployment.yaml` command.

With this structure, an enterprise user can download or git-clone the `ceneca` deployment package and have all necessary pieces in one place. Next, we’ll look at the configuration file in detail.

## Configuration: `config.yaml`

Ceneca uses a YAML configuration file (`config.yaml`) to define **all database connections, service credentials, and runtime settings**. The agent will automatically load this file at startup – looking first in the current directory, then in a default location like `~/.data-connector/config.yaml` if needed. This means as long as you place your edited `config.yaml` in the deployment folder (or your home directory under `.data-connector`), the system will find it without extra pointers. Keeping all configurable parameters in one file ensures that you have a single touchpoint for setup.

Below is a **sample `config.yaml`** covering typical settings. You should customize the values (notably credentials, hostnames, keys, etc.) for your environment:

```yaml
# Example Ceneca config.yaml for on-prem deployment

# 1. Database Connections (enterprise data sources)
postgres:
  uri: "postgresql://<USERNAME>:<PASSWORD>@<POSTGRES_HOST>:5432/<DB_NAME>"   # Primary Postgres DB:contentReference[oaicite:7]{index=7}
mongodb:
  uri: "mongodb://<USERNAME>:<PASSWORD>@<MONGO_HOST>:27017/<DB_NAME>"       # MongoDB connection URI:contentReference[oaicite:8]{index=8}
qdrant:
  uri: "http://<QDRANT_HOST>:6333"   # Qdrant vector DB endpoint (if using Qdrant for embeddings or similarity):contentReference[oaicite:9]{index=9}

# 2. Slack Integration (optional, for querying Slack messages via AI)
slack:
  mcp_url: "http://localhost:8500"   # URL of Slack MCP service (runs locally as a Docker service):contentReference[oaicite:10]{index=10}
  history_days: 30                  # How many days of Slack history to index for querying:contentReference[oaicite:11]{index=11}
  update_frequency: 6               # Hours between Slack channel schema refreshes:contentReference[oaicite:12]{index=12}
# (No Slack credentials/tokens here – Slack OAuth is handled via the MCP service at runtime)

# 3. Google Analytics 4 (optional, for querying GA4 analytics data)
ga4:
  key_file: "/etc/ceneca/ga4-service-account.json"   # Path to GA4 service account JSON key:contentReference[oaicite:13]{index=13}
  property_id: "<GA4_PROPERTY_ID>"                   # GA4 Property ID to query:contentReference[oaicite:14]{index=14}
  scopes:
    - https://www.googleapis.com/auth/analytics.readonly   # OAuth scope for GA4 API:contentReference[oaicite:15]{index=15}
  token_cache_db: "/var/lib/ceneca/ga4_tokens.sqlite"      # Path to SQLite for caching GA4 tokens (optional):contentReference[oaicite:16]{index=16}

# 4. LLM Provider Settings (for natural language queries)
llm:
  provider: "openai"                 # e.g., "openai" or "anthropic" or "azure-openai"
  model: "gpt-4-turbo"               # Model name (GPT-4 by default)
  api_key: "<YOUR_OPENAI_API_KEY>"   # API key for the LLM service
  # api_base: "<CUSTOM_API_BASE_URL>" # (optional) custom base URL if using Azure or others

# 5. Agent Service Settings
server:
  port: 8787    # Default HTTP port for Ceneca UI/API (users can override this if needed)
logging:
  level: "info" # Logging verbosity (info, debug, etc.)

# 6. Licensing (placeholder)
license_key: "XXXX-XXXX-XXXX-XXXX"   # Placeholder license key (for future validation logic)
```

A few notes on this configuration:

* **Database URIs:** We supply connection strings (URIs) for each data source. The example shows Postgres, MongoDB, and Qdrant URIs. If your organization uses only some of these, include only those sections. Ceneca will attempt to register any source that has a valid URI provided in this file. For example, if you include a `postgres.uri`, the system will load that into its source registry at startup. If a particular service is not used, you can omit it (or leave its `uri` blank/undefined).
* **Slack:** To enable Slack as a queryable source, include the `slack:` section. The `mcp_url` should point to the Slack MCP server’s address. In our default Docker setup, the Slack service runs locally on port 8500, hence `http://localhost:8500`. You can adjust `history_days` and `update_frequency` to control how much Slack message history is ingested and how often the system refreshes Slack channel data. **Important:** Slack API credentials (Client ID, Secret, etc.) are **not** stored in this file. Those will be provided via environment variables to the Slack MCP container for security. (We’ll cover that in deployment steps.) The Slack integration is designed so that after deployment, you’ll run an OAuth flow via the CLI to generate tokens – no sensitive user tokens are kept in config.
* **GA4:** If you want Ceneca to pull data from Google Analytics 4, provide a service account JSON and property ID. Typically, you would create a service account in GCP with Analytics Data Viewer roles, download the JSON key, and place it on the server (path specified in `ga4.key_file`). Ceneca will use that for server-to-server API access. The `scopes` are usually fine as given (read-only analytics). A local SQLite database can be used to cache GA4 query tokens (`token_cache_db`) to avoid frequent re-authentication; this is optional but recommended for performance.
* **LLM Settings:** By default, Ceneca uses OpenAI’s GPT-4 via API to translate natural language questions into database queries and insights. Enter your OpenAI API key (or Anthropic key, etc., if using an alternative). The `provider` can be changed if needed (for example, `"anthropic"` with corresponding `api_key` and `model`). All LLM calls are made from within your environment – only the query text and needed schema info are sent to the LLM API, and *no database records or PII are ever sent*.
* **Server Port:** The `server.port` is where Ceneca’s web service will listen. We default this to **8787** (an uncommon port to avoid conflicts, and easily memorable). You can change this if 8787 is in use or if you prefer another standard port. This setting will be used by the startup script/container to bind the service. (Internally, the code default might be 8080, but we override it here for clarity – any port is fine as long as it’s consistent.)
* **Logging:** You can adjust the log level (`info`, `debug`, etc.) to control verbosity. Logs will be printed to console by default or can be directed to a file if you add a `file` path under `logging`.
* **License Key:** We include a `license_key` field. In the current version, this is a **stub for future license validation**. You can put any string or your issued license key here. Upon startup, Ceneca will check this field – the **placeholder implementation** will perhaps log that a key was provided (or warn if not) but not enforce anything. This is designed to be extended in future (e.g., connecting to a license server or checking a signature) without changing how you deploy the software. For now, just treat it as a required field for completeness (you might use something like `ABC-1234-XYZ` format as a placeholder).

Once `config.yaml` is filled out, place it in the deployment directory (`ceneca/` in our example). During startup, the Ceneca agent will load this configuration automatically – no additional CLI flags or environment variables are needed to point to it (though you can override the config path via the `DATA_CONNECTOR_CONFIG` env var if absolutely necessary). Keeping all config in one YAML means it’s easy to version-control (if allowed) or share among your ops team, and there’s only one place to update when credentials or endpoints change.

## Deployment Methods

### Docker Deployment (Default)

Deploying Ceneca with Docker is the simplest and recommended approach. Docker encapsulates all necessary components and ensures a consistent environment. The provided `docker-compose.yml` defines the full stack – including the Ceneca agent and any supporting services (databases or integrations) – so you don’t have to start each piece manually. Below are the steps to deploy using Docker:

**1. Prerequisites:** Ensure the target machine (or VM) has **Docker** and **Docker Compose** installed and running. (On many systems, Docker Compose is integrated as `docker compose` command. This guide assumes you have it available.) No other system dependencies are required on the host, since all services will run in containers.

**2. Build or Fetch Docker Images:** You need Docker images for:

* **Ceneca Agent (Core)** – a Python-based service that runs the AI agent logic and the API server.
* **Slack MCP Service** (optional) – a small Flask/FastAPI service that handles Slack OAuth and data ingestion (only needed if Slack integration is used).
* Optionally, standard images for **PostgreSQL**, **MongoDB**, **Qdrant**, etc., if you choose to run these within Docker.

If your organization has access to pre-built images (for example, an official `ceneca/agent:latest` image on Docker Hub or an internal registry), you can pull them directly. Otherwise, you can build the images from the included Dockerfiles. For instance, in the `ceneca/` directory:

* Build the core agent image:

  ```bash
  docker build -t ceneca-agent:latest -f Dockerfile .
  ```

  This uses the `Dockerfile` which might look like:

  ```Dockerfile
  FROM python:3.10-slim
  WORKDIR /app
  COPY requirements.txt . 
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . . 
  EXPOSE 8787               # The agent will listen on 8787 by default
  CMD ["python", "main.py"] # Start the agent (which internally launches the web server)
  ```

  The above (especially the `EXPOSE` and `CMD`) ensures the container will run the agent on the expected port. The agent process will load `config.yaml` at startup as described earlier.

* Build the Slack MCP image (if needed):

  ```bash
  docker build -t ceneca-slack-mcp:latest -f Dockerfile.mcp ./ 
  ```

  The `Dockerfile.mcp` is provided to set up the Slack microservice. For example, it uses Python 3.11 and installs the Slack server requirements:

  ```Dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY ./agent/mcp/requirements.txt /app/requirements.txt
  RUN pip install --no-cache-dir -r /app/requirements.txt
  COPY . /app/
  EXPOSE 8500
  ENV PYTHONPATH=/app
  CMD ["python", "-m", "agent.mcp.server"]   # Launch Slack MCP server on port 8500
  ```

  This will run the Slack service that the main agent communicates with for Slack data. If you are not using Slack integration, you may skip building/running this image.

*Note:* The Docker Compose file is already set up to build these images for you if you use the `docker-compose build` command, so manually building with `docker build` is optional. You can simply rely on Compose to do it in the next step.

**3. Configure Environment & Secrets:** Before launching, ensure that any necessary secrets are provided to Docker. Most configuration is in `config.yaml`, but a few sensitive items (like Slack OAuth credentials) should be passed via environment variables. In the provided `docker-compose.yml`, you’ll find placeholders for Slack’s `MCP_SLACK_CLIENT_ID`, `MCP_SLACK_CLIENT_SECRET`, `MCP_SLACK_SIGNING_SECRET`, etc., in the Slack service section. Edit the compose file to insert your organization’s Slack App credentials (if Slack is enabled). Similarly, if using any custom credentials for internal databases (the default compose uses generic credentials for demo containers), update those in the compose or .env as needed. By keeping these in environment variables (or a `.env` file referenced by compose), you avoid hardcoding secrets in the config.yaml or code.

Also, the compose file mounts the config directory into the containers so that the `config.yaml` is accessible inside. For example, the Slack container uses:

```yaml
    volumes:
      - ~/.data-connector:/root/.data-connector
```

which means if you placed `config.yaml` in your home’s `.data-connector` folder, it will be available to the container at runtime. You can modify this path or add a similar mount for the main agent container (e.g., mount `./config.yaml` into `/app/config.yaml` or into `/root/.data-connector/` inside the agent container). In our default setup, we assume you’ll use the home directory mount as above for both services, or simply copy the config into the container image at build time. Ensure the container can read the config – that’s the main requirement here.

**4. Launch the Stack:** Now run the deployment. Using the provided script:

```bash
cd ceneca/
./deploy.sh
```

This script essentially calls Docker Compose to start everything. (If not using the script, you can run `docker-compose up -d` manually in the directory.) The first time you run this, Docker will build any images that are not already built (using the Dockerfiles) and then start all containers in the background (the `-d` flag).

Docker Compose will start multiple services as defined. For example, the default `docker-compose.yml` includes:

* **`ceneca-agent` service** (the main application container) – listening on port 8787 inside the container and mapped to host port 8787. It likely depends on other services being up (so it might have a `depends_on` for the databases).
* **`postgres` service** (optional) – a PostgreSQL 16 database container. In the compose, it is set up on port 5432 internally and mapped to host 6000 for debugging. It uses default credentials `dataconnector/dataconnector` and a default database name `dataconnector`. This is provided in case you need a local Postgres (for example, to cache certain data or if you don’t have an existing Postgres). If you intend to connect to an external enterprise Postgres (most cases), you might not need this container – you’d instead put your external DB URI in config.yaml and could remove or disable this service.
* **`mongodb` service** – a MongoDB 7 container on port 27017 (mapped to host 27000 in compose). It’s initialized with a user `dataconnector`/`dataconnector` and a database `dataconnector_mongo` for convenience. Like Postgres, this is optional if you already have a MongoDB you’re connecting to. The compose sets it up to make it easy to start a fresh Mongo instance for testing or for storing cached data.
* **`qdrant` service** – a Qdrant vector DB container. It uses a custom image build (to pre-load some initial data or configure storage) and by default listens on internal port 6333 HTTP (mapped to host 7500). This can be used by Ceneca for vector similarity queries or to store embeddings. If you’re using Qdrant features (like semantic search over text data or GA4 embeddings), this container provides the engine. If not, it can be omitted.
* **`slack-mcp-server` service** – the Slack integration service. It runs on port 8500 (mapped to host 8500 as well) and is responsible for handling the Slack OAuth flow and maintaining an index of Slack messages. The compose config passes in environment variables such as `MCP_HOST`, `MCP_PORT`, database creds for its internal use, and Slack API secrets. It also depends on two other containers:

  * **`postgres-mcp`** – a separate Postgres instance just for Slack OAuth data (running on port 5432 internally, host-mapped to 6500). The Slack service uses this to store Slack user tokens and session info. It’s initialized with credentials `slackoauth/slackoauth` and DB `slackoauth`.
  * **`slack-qdrant`** – a Qdrant instance dedicated to Slack message embeddings (running on 6333, host-mapped to 7750). This isolates Slack vector search from any other Qdrant usage.
* All these services are connected via a Docker network (`connector-network`) so they can communicate by container name internally. For instance, the agent container can reach the Postgres at hostname `postgres` (or as configured in the compose overrides) and the Slack service can reach its DB at `postgres-mcp`, etc. The config loader in the agent is aware of Docker mode and will use internal hostnames if it detects running in Docker (so you don’t have to change config URIs to the Docker names; it’s handled automatically when inside containers).

Once `docker-compose up -d` completes, run `docker-compose ps` (or `docker ps`) to verify all containers are up and healthy. The agent may take a few seconds to initialize – it might be loading AI models or building initial schema indexes for your databases. You can inspect logs with `docker-compose logs -f agent` (replace `agent` with the actual service name for ceneca agent in the compose, e.g., it might be `api` or similar if named so). Similarly, check logs for Slack MCP if it’s running, to see if it has started and is awaiting OAuth.

**5. Access the Service:** By default, the **Ceneca agent will be listening on port 8787** on the host. You can test this by visiting `http://localhost:8787` in a browser. (Depending on the product’s interface, you might see a simple web UI or an API endpoint. If a web GUI isn’t available yet, you’ll get a JSON response or similar indicating the service is running.) In enterprise use, you might not expose this port publicly – it could be within an internal network or behind a VPN. Adjust network settings as needed (for example, in Kubernetes you might put this behind a load balancer or ingress; in Docker, you might only allow certain IPs to access it, etc.).

**6. Overriding the Port:** If you need to change the port, update the `server.port` in config.yaml *and* the port mapping in the Docker Compose file (the left side of the mapping `HOST:CONTAINER`). For example, to use port 8080 instead, set `port: 8080` in config, and in compose do `"8080:8080"` mapping. The container’s internal port should match what the agent expects (which our Dockerfile exposes as 8787, but you can also set an environment variable `AGENT_PORT` inside the container to align with config). In summary, keep them consistent. The default 8787 is arbitrary; you are free to use 8080 or any open port.

**7. Stopping/Restarting:** You can stop the stack with `docker-compose down` (this will stop and remove containers, but because we used named volumes for persistence, your data in the Postgres/Mongo containers will persist between runs). To apply configuration changes, you’d typically edit `config.yaml`, then do `docker-compose down && docker-compose up -d --build` (the `--build` will rebuild images if you changed anything in the code or Dockerfiles). The agent will always read the latest config at startup, so this is all that’s needed to reconfigure it.

At this point, Ceneca is deployed and running locally via Docker. Next, we’ll cover how to interact with it (via the CLI or API) to test connections and ask questions. (We will describe Kubernetes and direct setups afterwards for those who need them.)

### Kubernetes Deployment (Alternative)

For enterprises using Kubernetes, Ceneca can be deployed on a cluster using the same Docker images. You might choose this route for better integration with your infrastructure (using K8s features for scaling, secrets management, monitoring, etc.). We provide a sample Kubernetes manifest (`k8s/ceneca-deployment.yaml`) that you can use as a starting point. This manifest defines all the necessary K8s objects: Deployments, Services, and Persistent Volumes.

**Key components in Kubernetes manifest:**

* **ConfigMap for `config.yaml`:** We recommend storing the content of your `config.yaml` in a Kubernetes ConfigMap, so that it can be mounted into the pods or read as environment variables. For example, the manifest might include:

  ```yaml
  apiVersion: v1
  kind: ConfigMap
  metadata:
    name: ceneca-config
  data:
    config.yaml: |
      (contents of your config.yaml here, indented appropriately)
  ```

  Later, in the pod spec for the agent, you can mount this config. For instance:

  ```yaml
        volumeMounts:
        - name: config-volume
          mountPath: /root/.data-connector/   # mounting as a directory
      volumes:
      - name: config-volume
        configMap:
          name: ceneca-config
          items:
            - key: config.yaml
              path: config.yaml
  ```

  This way, inside the container, the config will appear at `/root/.data-connector/config.yaml` (which, as noted, is one of the default paths the agent checks).

* **Secrets for sensitive data:** Similar to Docker, you should store sensitive keys (DB passwords, API keys, Slack secrets) in Kubernetes Secrets. For example, create a secret for Slack:

  ```yaml
  apiVersion: v1
  kind: Secret
  metadata:
    name: ceneca-slack-secrets
  type: Opaque
  stringData:
    SLACK_CLIENT_ID: "<your Slack app client ID>"
    SLACK_CLIENT_SECRET: "<your Slack app client secret>"
    SLACK_SIGNING_SECRET: "<your Slack signing secret>"
  ```

  and so on. Then reference these in the Slack Deployment via environment variables from secret.

* **Deployments for each service:** Each container from the Docker Compose file will correspond to a Deployment in K8s (or a StatefulSet for the databases if we want stable storage and consistent naming).

  For brevity, we’ll illustrate just the **Ceneca agent** deployment and service:

  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: ceneca-agent
    labels:
      app: ceneca
      role: agent
  spec:
    replicas: 1
    selector:
      matchLabels:
        app: ceneca
        role: agent
    template:
      metadata:
        labels:
          app: ceneca
          role: agent
      spec:
        containers:
        - name: agent
          image: ceneca-agent:latest  # ensure this image is available in your registry/cluster
          imagePullPolicy: IfNotPresent
          ports:
          - containerPort: 8787
            name: http
          env:
          - name: AGENT_PORT
            value: "8787"
          - name: LLM_API_KEY               # example of passing the LLM key via env (from secret)
            valueFrom:
              secretKeyRef:
                name: ceneca-llm-secret
                key: OPENAI_API_KEY
          # ... (other environment variables or secret refs as needed)
          volumeMounts:
          - name: config-volume
            mountPath: /root/.data-connector/
        volumes:
        - name: config-volume
          configMap:
            name: ceneca-config
            items:
              - key: config.yaml
                path: config.yaml
  ---
  apiVersion: v1
  kind: Service
  metadata:
    name: ceneca-agent-service
  spec:
    type: ClusterIP  # or LoadBalancer if exposing externally
    selector:
      app: ceneca
      role: agent
    ports:
      - port: 8787        # cluster port
        targetPort: 8787  # container port
        protocol: TCP
        name: http
  ```

  In the above, the Deployment runs the ceneca agent container, mounts the config from the ConfigMap, and sets the necessary environment (like `AGENT_PORT` and any keys). The Service exposes it on the cluster. If you need external access, you might use `type: LoadBalancer` or an Ingress to route to this service.

  You would create similar Deployments for the other pieces: one for `postgres` (with a PersistentVolumeClaim for data), one for `mongodb` (with a volume), one for `qdrant`, one for `slack-mcp-server`, etc. Each can be configured with the same parameters as in Docker (use the same images, environment variables, and mount the config if needed). For instance:

  * A Postgres Deployment using `postgres:16` image, with env `POSTGRES_USER=dataconnector` etc., and a PVC for `/var/lib/postgresql/data`.

  * A MongoDB Deployment using `mongo:7`, with `MONGO_INITDB_ROOT_USERNAME` env, and PVC for `/data/db`.

  * A Qdrant Deployment using `qdrant/qdrant:latest`, with persistent storage volume.

  * A Slack MCP Deployment using `ceneca-slack-mcp:latest` image, with env vars for Slack credentials drawn from the secret, and perhaps a ConfigMap for other settings (like `MCP_PORT=8500`, etc.), plus Service on 8500 (ClusterIP).

  * Slack Postgres (for OAuth) – could reuse the main Postgres by creating a separate database on it, or deploy another Postgres instance. In our Docker setup it was separate, but on K8s you might not need two separate Postgres if you can isolate by schema.

  > **Tip:** Instead of writing many YAML sections, you can use a Helm chart or Kustomize to templatize this deployment. A Helm chart could allow enabling/disabling components (e.g., include Slack sub-chart only if Slack is needed) and help manage secrets. For this blueprint, the static manifest is a straightforward translation of the Docker Compose into K8s objects.

* **Apply and verify:** Once you have the manifest ready (with all necessary adjustments for your environment, such as image registry paths and secret values), apply it: `kubectl apply -f ceneca-deployment.yaml`. Kubernetes will pull up the pods. You can check `kubectl get pods` to watch the status. The agent pod should start and register ready (it might take a little time on first launch as it builds indices or connects to databases). Ensure that the DB pods (Postgres/Mongo) reach Running state before the agent (the agent Deployment can include an `initContainer` or startup probe to wait for DB availability, or simply the agent will retry on failures).
  Check logs with `kubectl logs deployment/ceneca-agent -f` for any issues (e.g., misconfigured connection string). Common issues might be network (if connecting to an external DB, ensure the cluster can reach it or the DB is deployed in cluster as well).

* **Networking:** By default, we used a ClusterIP service for the agent, which means it’s accessible within the cluster. To allow users to access Ceneca’s interface, you might expose it via:

  * A **LoadBalancer Service:** change the Service type to LoadBalancer to get a cloud LB IP (if in cloud) or use MetalLB on-prem.
  * An **Ingress:** create an Ingress resource mapping some URL (like `ceneca.company.com`) to the ceneca-agent-service on port 8787. Don’t forget to handle TLS if exposing externally.
  * **Port-forwarding:** for quick tests, you can do `kubectl port-forward svc/ceneca-agent-service 8787:8787` to access it from your local machine.

Kubernetes deployment gives you flexibility to scale components (though likely you’ll keep a single agent instance unless load demands multiple replicas for read queries). It also allows using native secrets and config management to keep things secure. The trade-off is complexity – hence for initial setup or smaller scale, Docker Compose is often easier.

### Direct Local Execution (Advanced/Optional)

If Docker or Kubernetes are not viable (or if your devs want to run Ceneca directly for development or debugging), you can run the agent and services directly on a host machine. This method requires more manual setup, but we outline it for completeness:

1. **Environment Setup:** Install **Python 3.10+** on the machine. Also install any database servers you plan to use (or ensure connectivity to them). For example, if you want to connect to a local Postgres, have it installed and running. For Qdrant, you might use a Docker container or install it from binary (Qdrant can run as a standalone process but it’s non-trivial to install from source – using Docker even in this case might be easier).
2. **Install Ceneca:** Obtain the Ceneca code (e.g., clone the `data-connector` repository which contains the agent code). It’s structured as a Python package. You can install the requirements:

   ```bash
   cd data-connector/server
   pip install -r requirements.txt
   ```

   (It’s recommended to do this in a Python virtual environment.) Optionally, there may be a PyPI package in the future (e.g., `pip install ceneca`), but for now using the source is fine.
3. **Run Migrations/Setup (if any):** The agent does not use an internal database that requires migration (its needed schemas are built at runtime), so you likely don’t have a migration step. If using Slack, you should set up a Postgres database for Slack OAuth data. You could reuse an existing Postgres instance – create a database `slackoauth` and user `slackoauth` with password, matching what the Slack service expects (or adjust the Slack service config to your DB credentials).
4. **Start the Agent:** Simply run the main Python entry point. In the repository, that is `server/main.py` which launches the FastAPI/UVicorn server. For example:

   ```bash
   export AGENT_PORT=8787  # if you want to override default port in lieu of config
   python server/main.py
   ```

   This should start the web server on localhost:8787 (check the console logs for "Running on [http://0.0.0.0:8787](http://0.0.0.0:8787)" or similar). The agent will load `config.yaml` from `~/.data-connector/` or the current directory, so ensure your config file is in one of those places. Alternatively, you can set an env var `DATA_CONNECTOR_CONFIG=/path/to/config.yaml` to point it explicitly.
5. **Start Slack MCP (if needed):** The Slack integration server must be run as a separate process. You can start it by running the module `agent.mcp.server`. For example:

   ```bash
   export MCP_PORT=8500
   export MCP_DB_HOST=<your slack pg host> MCP_DB_NAME=slackoauth MCP_DB_USER=slackoauth MCP_DB_PASSWORD=<pwd>
   export MCP_SLACK_CLIENT_ID=<...> MCP_SLACK_CLIENT_SECRET=<...> MCP_SLACK_SIGNING_SECRET=<...>
   python -m agent.mcp.server
   ```

   (Yes, a lot of environment variables; this is why using Docker Compose is easier! You might script this in a shell script for convenience.) This will start the Slack service on 8500. Make sure 8500 is accessible to the agent (if on the same machine, localhost:8500 as config implies).
6. **Verify and Use:** Once both processes are running (agent and Slack service), you can interact the same way as in Docker. The advantage of direct execution is easier debugging and not needing Docker, but the disadvantage is manually managing dependencies and services.

**Note:** For production use, we strongly encourage using Docker or Kubernetes to manage the processes. They handle restarts, logs, resource limits, etc., more gracefully. Running directly might be okay for development or in a pinch, but you’d have to set up your own systemd service or supervisor to keep the agent running in the background, handle crashes, etc. The Docker/K8s route encapsulates that operational overhead.

## Usage: Testing and Operating Ceneca

After deployment, enterprise users can interact with Ceneca through a **command-line interface (CLI)** or via HTTP requests (if integrating with other tools). Here we focus on the CLI usage, as it’s the most straightforward way to test and leverage the data connector functionality.

Assuming Ceneca is up and running (via Docker or other method), you can use the CLI to perform tasks like testing connections, loading schemas, and asking questions. If you deployed with Docker Compose, you might run the CLI by entering the agent container, or by using a provided wrapper script. For instance: `docker exec -it ceneca-agent /bin/bash` to get a shell, then running commands inside. If you installed Ceneca as a Python package or via pip, you might have a `ceneca` command available on your system. (Alternatively, running `python server/agent/cmd/query.py` with arguments is possible, but let's assume a nicer interface exists.)

Here are some common CLI interactions with examples:

* **Test Database Connection:** Verify that Ceneca can reach your databases. Use the `test-connection` command to ping the DB. For example:

  ```bash
  ceneca test-connection --type postgres
  ```

  This will attempt to connect to the Postgres database configured in `config.yaml` (or you can override the URI with `--uri` flag). The CLI will output something like: *"Testing connection to **postgres** database..."* and then either a success message or error. For a MongoDB, you could do `ceneca test-connection --type mongodb`, etc. This is a quick way to ensure your credentials in config are correct and the network connectivity is okay, before doing actual queries.

* **Initialize Schema (if needed):** On first run, Ceneca will introspect your databases to learn their schema (table names, columns, etc.) and build an internal index (possibly a vector index for semantic search on schema). This usually happens automatically when you run a query. You might see logs like *"Building schema index for Postgres..."*. If you want to manually force a schema refresh, there may be a command for that (e.g., something like `ceneca refresh-schema` or it might be part of `test-connection`). Check documentation – in many cases, just running the first query triggers it. For Slack, you have a separate flow (see Slack section below).

* **Natural Language Query:** The main feature – ask a question in plain English. For example:

  ```bash
  ceneca query "Show me the total sales by region for the last quarter"
  ```

  The CLI will identify which data source to use (if you have multiple, it uses the default or you can specify `--type`). It will then use the LLM to translate this into a SQL query (for a database) or appropriate API calls, execute them, and then either display the results or a summary. The output might be a table of results, or a narrative insight depending on the query. For instance, you might get a table of regions and sales figures, followed by an AI-generated sentence like "North America had the highest sales with \$X." The CLI uses rich formatting to present results; by default the output is in Markdown format for readability. You can pipe the output to a file or wrap it in a script for automated analysis.

  If you have multiple databases connected, you can target one explicitly:

  ```bash
  ceneca query --type mongodb "How many users signed up in the last week?"
  ```

  This will direct the question to the MongoDB source (maybe translating it to a MongoDB aggregation pipeline under the hood). If not sure, Ceneca uses the `default_database` setting (in config, defaults to Postgres if not set) to decide which adapter to use when `--type` is not provided.

  **Cross-Database Queries:** A more advanced capability is to query across multiple sources at once (e.g., ask a question that requires combining data from Postgres and Mongo). The architecture for this is in place – Ceneca’s orchestrator can in theory gather info from different adapters. However, in practice such queries are complex. Initially, focus on one source at a time or handle integration in the question itself (the AI might fetch from one DB then the other). This area is evolving.

* **Slack Integration Workflow:** If you have Slack configured, there are a couple extra steps to use it:

  1. **Authenticate with Slack:** Run `ceneca slack auth`. This will initiate an OAuth flow – typically it will print a URL or even open a browser for you to authorize the Ceneca Slack app for your workspace. Follow the prompts in the browser (log into Slack and approve). The CLI will wait and once you complete the auth, the Slack MCP server will receive the tokens and the CLI will store credentials locally (e.g., under `~/.data-connector/` for reuse). This one-time step bootstraps the Slack connection.
  2. **List Slack Workspaces (optional):** If your Slack token has access to multiple workspaces, you can run `ceneca slack list-workspaces` to see which ones are linked and choose a default. In a single-workspace scenario, this isn’t needed.
  3. **Query Slack data:** Now you can query Slack similar to a database. For example:

     ```bash
     ceneca query --type slack "How many messages were posted in #general this week?"
     ```

     The system will use the Slack adapter to interpret this. Under the hood, it might translate to Slack Web API calls or search queries. The result could be a number or list of messages. The idea is you can get insights like "There were 123 messages in #general this week, a 10% increase from last week."
     Another Slack-specific command is `ceneca slack refresh` which forces re-indexing of Slack channels (if you suspect new channels or changes that the agent hasn’t picked up). The Slack data (channels, message counts, etc.) is periodically updated as per `update_frequency` in config, but you can manually trigger it via CLI if needed.

  Slack queries allow you to treat unstructured communication data similarly to structured database data, using natural language. This can be powerful for questions like "What issues are people most frequently discussing in support channels?" etc. Keep in mind Slack API rate limits and the `history_days` setting – by default it only indexes the last 30 days to keep things efficient.

* **Google Analytics Queries:** If GA4 is configured, you can ask questions about web/app analytics. For example:

  ```bash
  ceneca query "What was the 7-day active users count last week compared to the week prior (GA4)?"
  ```

  The agent will recognize that this question pertains to GA4 data (especially if the question explicitly mentions GA or uses metrics/dimensions from GA4). It will then use the GA4 adapter to fetch data via the Google Analytics API. The results might be given as a numeric comparison and an AI-generated summary like "Users in the last week were 12% higher than the previous week". There isn’t a separate `--type ga4` flag currently – the system decides based on context, or you could specify if implemented. Ensure the service account has access to the GA4 property and that your machine can reach the Google APIs (outbound HTTPS) – since this is on-prem, your firewall must allow that egress.

* **Command-line Examples Summary:** To recap, here are example commands an enterprise user might run after deployment:

  * `ceneca test-connection --type postgres` – *Test connectivity to the Postgres DB configured.*
  * `ceneca test-connection --type mongodb` – *Test connectivity to MongoDB.*
  * `ceneca query "List the top 5 products by sales in Q1 2025"` – *Query default DB (say Postgres) for a business question.*
  * `ceneca query --type qdrant "Find similar customer feedback to 'great service'."` – *Perform a semantic similarity search on a Qdrant vector store if configured (this assumes you’ve ingested text data into Qdrant).*
  * `ceneca slack auth` – *Initiate Slack authentication flow.*
  * `ceneca query --type slack "Who were the most active Slack users this month?"` – *Ask Slack data question after auth (MCP will handle the heavy lifting).*
  * `ceneca query "Give me a summary of website user growth vs sales (GA4 vs Postgres)"` – *Example of a cross-source query (advanced). The agent might fetch user counts from GA4 and sales from Postgres and then combine the insight.*

These examples illustrate how an end-user (data analyst or business user with access to the CLI) can interact with the deployed agent. The CLI is designed to be user-friendly, with help texts and descriptive outputs. In a production setting, you might integrate this with other tools – e.g., call the API from a BI dashboard or integrate the Slack query capability into Slack itself via a bot. The possibilities extend beyond the CLI, but the CLI is the primary admin and testing interface.

## License Key Validation Stub

Ceneca’s deployment includes a placeholder for license key checking. In this blueprint, we treat the `license_key` in `config.yaml` as the input for that mechanism. The current implementation does **not** enforce license restrictions – it simply logs the presence of a key or not. For example, when the agent starts up, it may read the `license_key` from config and do a basic check like:

```python
license = config.get('license_key')
if license:
    logger.info(f"License key {license} provided. (Validation stub - not enforced)")
else:
    logger.warning("No license key provided! Running in unlicensed mode (stub).")
```

This is a trivial check (and might not exactly exist in the code yet), but it shows the intention. As an enterprise user, you are asked to include the license key you’ve been given (or a trial key) in the config. In future updates, that key might be validated against an offline signature or an online verification service to ensure you’re authorized to run the software. The validation logic can be updated in the agent’s startup sequence without changing how you deploy – you will still just supply the key in the same config file. For now, you won’t experience any difference whether the key is valid or not (hence “stub”). Just make sure to put some placeholder string there so that when real validation is introduced, you won’t accidentally be locked out for missing key.

From an architectural standpoint, placing the license check in the application (rather than in the container, etc.) means your deployment process doesn’t change with licensing – you’re always editing only the config file. This aligns with our principle: **`config.yaml` is the only file you ever need to touch** for configuring Ceneca.

## Enterprise Readiness and Next Steps

By following this blueprint, an enterprise can deploy Ceneca on a single server or across a cluster, configure it to connect to all relevant data sources, and start querying data in natural language – all within their firewall. A quick recap of why this is enterprise-ready:

* **On-Prem and Secure:** All components run on infrastructure you control (your servers or cloud instances). No sensitive data leaves your environment. Even when using cloud LLM APIs, only query metadata is sent (no raw tables) and you can opt to use on-prem LLMs if needed by adjusting config.
* **Single Config File:** All integration points (DB creds, API keys, etc.) are centralized in `config.yaml`, which can be managed via your usual secret management process. This reduces the chance of misconfiguration and makes audits easier.
* **Docker/K8s Deployment:** Containerization ensures consistency across dev, staging, prod. The default Docker Compose setup is easy to spin up for a quick POC or pilot. Kubernetes support means it can fit into more complex enterprise deployment pipelines (with Helm charts, CI/CD, etc.).
* **Scalability:** You can scale vertically by allocating more resources to the agent container (for handling bigger queries or more concurrent usage), or horizontally by running multiple agent replicas behind a load balancer (if the stateless query processing allows it – ensure any in-memory indexes or caches are shared or rebuilt per replica). The databases themselves can be scaled as they normally would (since Ceneca just connects to them).
* **Extensibility:** New data sources can be added by configuring their connection in the YAML (and ensuring an adapter is available in the code). The blueprint already includes Slack and GA4 which are non-traditional sources, showing the flexibility of the system. The architecture supports adding things like Elasticsearch, Redis, or other APIs fairly easily in the future. You can enable/disable sources without redeploying the whole system – just edit config and restart the agent.
* **Maintenance:** Routine updates (new versions of Ceneca) would typically mean updating the Docker image. This can be done by pulling a new image and re-launching, or building from updated code. Because config is externalized and data is in external systems or mounted volumes, you can upgrade containers without losing state (Slack indexes, etc., are either re-computed or stored in volumes like the `schema-registry-data` volume used in Docker Compose to persist the schema registry between runs).

Finally, always refer to the official documentation and support channels for Ceneca (for example, the website **ceneca.ai** or the GitHub repo README) for any product-specific nuances. This blueprint is a comprehensive starting point. With this in place, enterprise users can confidently install Ceneca on-prem and immediately begin asking questions to their databases and services in natural language – unlocking insights while keeping data secure within their own environment.

**Sources:**

* Ceneca product constants and features
* Data Connector configuration loader and usage of `config.yaml`
* GA4 integration documentation (service account config example)
* Slack integration documentation (config and CLI usage)
* Docker Compose configuration for Slack service and Qdrant (showing default ports and volumes)
* CLI command definitions and help text (test connection, etc.)
