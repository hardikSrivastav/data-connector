#!/bin/bash

# Generate self-signed SSL certificates for development
# For production, use proper certificates from a trusted CA

# Set variables
DOMAIN=${1:-localhost}
CERT_DIR="./nginx/ssl"
DAYS=${2:-365}

# Ensure the SSL directory exists
mkdir -p "$CERT_DIR"

echo "Generating self-signed SSL certificate for domain: $DOMAIN"
echo "Certificate will be valid for $DAYS days"

# Generate private key
openssl genrsa -out "$CERT_DIR/key.pem" 2048

# Generate certificate signing request
openssl req -new -key "$CERT_DIR/key.pem" -out "$CERT_DIR/csr.pem" -subj "/CN=$DOMAIN/O=Ceneca/C=US"

# Generate self-signed certificate
openssl x509 -req -days $DAYS -in "$CERT_DIR/csr.pem" -signkey "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem"

# Remove CSR as it's no longer needed
rm "$CERT_DIR/csr.pem"

echo "Self-signed SSL certificate generated:"
echo "Private key: $CERT_DIR/key.pem"
echo "Certificate: $CERT_DIR/cert.pem"
echo ""
echo "NOTE: For production use, replace these with proper certificates from a trusted CA." 