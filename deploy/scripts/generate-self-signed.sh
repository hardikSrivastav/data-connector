#!/bin/bash

# Generate self-signed SSL certificate for testing
set -e

DOMAIN=${1:-ceneca.localhost}

echo "Generating self-signed SSL certificate for $DOMAIN"

# Create certs directory if it doesn't exist
mkdir -p certs

# Generate private key
openssl genrsa -out certs/private.key 2048

# Generate certificate signing request
openssl req -new -key certs/private.key -out certs/certificate.csr -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"

# Create certificate extensions file
cat > certs/certificate.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = localhost
DNS.3 = *.$(echo $DOMAIN | cut -d. -f2-)
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate self-signed certificate (valid for 1 year)
openssl x509 -req -in certs/certificate.csr -signkey certs/private.key -out certs/certificate.crt -days 365 -extensions v3_req -extfile certs/certificate.ext

# Set proper permissions
chmod 600 certs/private.key
chmod 644 certs/certificate.crt

# Clean up temporary files
rm certs/certificate.csr certs/certificate.ext

echo "✅ Self-signed certificate generated:"
echo "   Certificate: certs/certificate.crt"
echo "   Private key: certs/private.key"
echo ""
echo "⚠️  WARNING: This is a self-signed certificate for testing only!"
echo "   Your browser will show security warnings."
echo "   For production, use a certificate from a trusted CA." 