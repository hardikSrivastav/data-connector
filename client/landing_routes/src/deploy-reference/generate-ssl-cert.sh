#!/bin/bash

# Set the domain for the SSL certificate
DOMAIN=${CENECA_DOMAIN}

# Generate a self-signed SSL certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/ceneca.key \
  -out /etc/ssl/certs/ceneca.crt \
  -subj "/CN=$DOMAIN"