FROM qdrant/qdrant:latest

# Install Python and pip + curl
RUN apt-get update && \
    apt-get install -y python3 python3-pip curl python3.11-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Set up working directory
WORKDIR /qdrant/init

# Install required Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy initialization scripts
COPY . .

# Make init script executable
RUN chmod +x init.sh

# Set the entrypoint to use our custom initialization script
ENTRYPOINT ["/bin/bash", "-c", "(/qdrant/init/init.sh &) && /qdrant/qdrant"] 