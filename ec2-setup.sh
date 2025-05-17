#!/bin/bash

# Update packages
echo "Updating system packages..."
sudo yum update -y || sudo apt update -y

# Install Docker
echo "Installing Docker..."
if command -v apt &> /dev/null; then
    # Ubuntu/Debian
    sudo apt install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
elif command -v yum &> /dev/null; then
    # Amazon Linux
    sudo yum install -y docker
    sudo service docker start
    sudo chkconfig docker on
    sudo amazon-linux-extras install docker -y
fi

# Add current user to docker group
echo "Adding user to docker group..."
sudo usermod -aG docker $USER

# Install Docker Compose
echo "Installing Docker Compose..."
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create app directory
echo "Creating application directory..."
mkdir -p ~/app
cd ~/app

# Clone repository (replace with your repository URL)
echo "Please enter your git repository URL:"
read REPO_URL
git clone $REPO_URL .

echo "Setup complete! Please remember to set your environment variables before running docker-compose."
echo "You may need to log out and back in for docker group membership to take effect." 