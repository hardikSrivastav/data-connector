#!/bin/bash
set -e

# Ceneca Agent Build and Publish Script
# This script builds the Ceneca agent Docker image and pushes it to a registry
# Run this script from the project root directory

# Configuration
IMAGE_NAME="hardiksriv/agent"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"

# Detect registry (optional)
REGISTRY=""  # Leave empty for Docker Hub
#REGISTRY="your-registry.example.com/"  # Uncomment for private registry

if [ ! -z "$REGISTRY" ]; then
    FULL_IMAGE_NAME="$REGISTRY$FULL_IMAGE_NAME"
fi

# Display banner
echo "==============================================================="
echo "        Ceneca Agent - Build and Publish Tool                  "
echo "==============================================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Ensure we're in the project root directory
if [ ! -d "server" ] || [ ! -d "deploy" ]; then
    echo "Error: This script must be run from the project root directory."
    echo "Current directory does not look like the project root."
    exit 1
fi

# Ensure the Dockerfile exists
if [ ! -f "deploy/Dockerfile" ]; then
    echo "Error: Dockerfile not found at deploy/Dockerfile"
    exit 1
fi

# Build the Docker image
echo "Building Docker image: $FULL_IMAGE_NAME"
docker build -f deploy/Dockerfile -t "$FULL_IMAGE_NAME" .

# Ask if we should push to registry
echo ""
read -p "Do you want to push this image to the registry? (y/n): " push_image

if [ "$push_image" = "y" ] || [ "$push_image" = "Y" ]; then
    # Check if logged in to Docker registry
    if [ -z "$REGISTRY" ]; then
        echo "Checking Docker Hub login status..."
        # Better way to check Docker Hub login status
        if ! docker login --help &>/dev/null; then
            # If docker login fails to even run, something is wrong
            echo "Error: Unable to check Docker Hub login status."
            exit 1
        fi
        
        # Try a token verification test
        if ! docker buildx inspect &>/dev/null; then
            echo "You may not be logged in to Docker Hub or authorization issue encountered."
            echo "Please try: docker login"
            read -p "Continue anyway? (y/n): " continue_anyway
            if [ "$continue_anyway" != "y" ] && [ "$continue_anyway" != "Y" ]; then
                exit 1
            fi
        else
            echo "Docker credentials found. Continuing with push."
        fi
    else
        echo "Using custom registry: $REGISTRY"
        echo "Ensure you are logged in to this registry if required."
    fi
    
    echo "Pushing image to registry: $FULL_IMAGE_NAME"
    docker push "$FULL_IMAGE_NAME"
    
    echo ""
    echo "Image successfully pushed to registry!"
    echo "Enterprise customers can now pull it with: docker pull $FULL_IMAGE_NAME"
else
    echo ""
    echo "Image built successfully but not pushed to registry."
    echo "You can push it later with: docker push $FULL_IMAGE_NAME"
fi

echo ""
echo "==============================================================="
echo "                       Build Complete                          "
echo "==============================================================="

# Instructions for enterprise deployment
echo ""
echo "To prepare an enterprise deployment package:"
echo ""
echo "1. Create a new directory for your enterprise package:"
echo "   mkdir -p ceneca-enterprise-package"
echo ""
echo "2. Copy the enterprise files to the package:"
echo "   cp deploy/enterprise-docker-compose.yml ceneca-enterprise-package/docker-compose.yml"
echo "   cp deploy/enterprise-install.sh ceneca-enterprise-package/install.sh"
echo "   cp deploy/sample-config.yaml ceneca-enterprise-package/sample-config.yaml"
echo "   chmod +x ceneca-enterprise-package/install.sh"
echo ""
echo "3. Package and distribute to enterprise customers:"
echo "   tar -czf ceneca-enterprise-deployment.tar.gz ceneca-enterprise-package"
echo ""
echo "Customers can then extract and run the installation script:"
echo "   tar -xzf ceneca-enterprise-deployment.tar.gz"
echo "   cd ceneca-enterprise-package"
echo "   ./install.sh"
echo "" 