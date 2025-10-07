#!/bin/bash
# Create a complete deployment package for air-gapped environments

set -e

VERSION=${1:-latest}
OUTPUT_DIR="ceneca-deployment-v${VERSION}"
ARCHIVE_NAME="${OUTPUT_DIR}.tar.gz"

echo "🎁 Creating Ceneca deployment package..."

# Create package directory
mkdir -p "${OUTPUT_DIR}"

# 1. Save Docker image
echo "📦 Saving Docker image..."
docker pull hardiksriv/agent:${VERSION}
docker save hardiksriv/agent:${VERSION} | gzip > "${OUTPUT_DIR}/ceneca-agent.tar.gz"

# 2. Copy deployment files
echo "📋 Copying deployment files..."
cp docker-compose.yml "${OUTPUT_DIR}/"
cp README.md "${OUTPUT_DIR}/"
cp -r config "${OUTPUT_DIR}/"
cp -r scripts "${OUTPUT_DIR}/"
cp -r certs "${OUTPUT_DIR}/"

# 3. Create installation script for customer
cat > "${OUTPUT_DIR}/install.sh" << 'EOF'
#!/bin/bash
# Ceneca Enterprise Installation Script

set -e

echo "🚀 Installing Ceneca Enterprise..."

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install it first."
    exit 1
fi

# Load Docker image
echo "📦 Loading Ceneca image..."
if [ -f ceneca-agent.tar.gz ]; then
    gunzip -c ceneca-agent.tar.gz | docker load
    echo "✅ Image loaded successfully"
else
    echo "❌ ceneca-agent.tar.gz not found"
    exit 1
fi

# Setup configuration
echo "⚙️  Setting up configuration..."
if [ ! -f config/config.yaml ]; then
    cp config/config.yaml.example config/config.yaml
    echo "📝 Created config/config.yaml - Please edit with your settings"
fi

if [ ! -f config/auth-config.yaml ]; then
    cp config/auth-config.yaml.example config/auth-config.yaml
    echo "📝 Created config/auth-config.yaml - Please configure SSO"
fi

# Check SSL certificates
if [ ! -f certs/certificate.crt ] || [ ! -f certs/private.key ]; then
    echo "⚠️  No SSL certificates found. Generating self-signed for testing..."
    ./scripts/generate-self-signed.sh localhost
    echo "⚠️  WARNING: Using self-signed certificate. Replace with real certificate for production!"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Edit config/config.yaml with your database credentials"
echo "  2. Edit config/auth-config.yaml with your SSO settings"
echo "  3. Replace SSL certificates in certs/ folder (if needed)"
echo "  4. Run: docker-compose up -d"
echo "  5. Test: ./scripts/test-deployment.sh"
echo ""
EOF

chmod +x "${OUTPUT_DIR}/install.sh"
chmod +x "${OUTPUT_DIR}/scripts/"*.sh

# 4. Create archive
echo "📦 Creating archive..."
tar -czf "${ARCHIVE_NAME}" "${OUTPUT_DIR}"

# Cleanup
rm -rf "${OUTPUT_DIR}"

echo ""
echo "✅ Deployment package created: ${ARCHIVE_NAME}"
echo ""
echo "Package size: $(du -h "${ARCHIVE_NAME}" | cut -f1)"
echo ""
echo "📧 Send this file to your customer:"
echo "   ${ARCHIVE_NAME}"
echo ""
echo "They should run:"
echo "   tar -xzf ${ARCHIVE_NAME}"
echo "   cd ${OUTPUT_DIR}"
echo "   ./install.sh"
echo "   # Edit configs"
echo "   docker-compose up -d"
echo ""


