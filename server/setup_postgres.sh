#!/bin/bash

# PostgreSQL Setup Script for Notion Clone
echo "Setting up PostgreSQL for Notion Clone..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Please install it first:"
    echo ""
    echo "On macOS: brew install postgresql"
    echo "On Ubuntu: sudo apt-get install postgresql postgresql-contrib"
    echo "On Windows: Download from https://www.postgresql.org/download/windows/"
    echo ""
    exit 1
fi

# Check if PostgreSQL service is running
if ! pg_isready -q; then
    echo "Starting PostgreSQL service..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew services start postgresql
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
    
    # Wait for PostgreSQL to start
    sleep 3
fi

# Create user and database
echo "Creating database user and database..."

# Create user (if doesn't exist)
sudo -u postgres psql -c "CREATE USER notion_user WITH PASSWORD 'notion_password';" 2>/dev/null || echo "User notion_user already exists"

# Create database (if doesn't exist)
sudo -u postgres psql -c "CREATE DATABASE notion_clone OWNER notion_user;" 2>/dev/null || echo "Database notion_clone already exists"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE notion_clone TO notion_user;"

echo "Testing database connection..."
if PGPASSWORD=notion_password psql -h localhost -U notion_user -d notion_clone -c "\q" 2>/dev/null; then
    echo "✅ Database connection successful!"
    echo ""
    echo "Database Details:"
    echo "Host: localhost"
    echo "Port: 5432"
    echo "Database: notion_clone"
    echo "Username: notion_user"
    echo "Password: notion_password"
    echo ""
    echo "Connection URL: postgresql://notion_user:notion_password@localhost:5432/notion_clone"
else
    echo "❌ Database connection failed. Please check your PostgreSQL installation."
    exit 1
fi

echo "✅ PostgreSQL setup complete!" 