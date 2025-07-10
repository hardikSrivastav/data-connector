#!/bin/bash

# Set the domain for the SSL certificate
DOMAIN=${CENECA_DOMAIN}

# Generate SSL certificate
bash generate-ssl-cert.sh

# Start the Ceneca deployment
docker-compose -f ceneca-docker-compose.yml up -d