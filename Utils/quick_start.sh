#!/bin/bash

# Quick Start Script for Polish Stocks Database Setup
# This script automates the initial setup process

set -e  # Exit on any error

echo "============================================================"
echo " Polish Stocks Database - Quick Start Setup"
echo "============================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "✗ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "✗ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 is not installed. Please install Python 3.9+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python $PYTHON_VERSION is installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo "⚠  Please edit .env and change DB_PASSWORD before production use!"
else
    echo "✓ .env file already exists"
fi

# Create init_db directory if it doesn't exist
if [ ! -d init_db ]; then
    echo ""
    echo "Creating init_db directory..."
    mkdir -p init_db
    echo "✓ init_db directory created"
fi

# Start Docker containers
echo ""
echo "Starting PostgreSQL database container..."
docker-compose up -d

# Wait for database to be ready
echo ""
echo "Waiting for database to be ready..."
sleep 5

# Check if database is healthy
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker-compose exec -T postgres pg_isready -U trader -d polish_stocks &> /dev/null; then
        echo "✓ Database is ready!"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "  Waiting... (attempt $ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "✗ Database failed to start. Check logs with: docker-compose logs"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
python3 -m pip install -q -r requirements.txt
echo "✓ Python dependencies installed"

# Run verification script
echo ""
echo "Running setup verification..."
python3 verify_setup.py

# Ask if user wants to load data
echo ""
echo "============================================================"
read -p "Do you want to load historical data now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Loading historical data..."
    python3 load_data.py
fi

echo ""
echo "============================================================"
echo " Setup Complete!"
echo "============================================================"
echo ""
echo "Database is running and ready to use."
echo ""
echo "Useful commands:"
echo "  - View logs:        docker-compose logs -f"
echo "  - Stop database:    docker-compose down"
echo "  - Start database:   docker-compose up -d"
echo "  - Connect to DB:    docker exec -it polish_stocks_db psql -U trader -d polish_stocks"
echo "  - Load data:        python3 load_data.py"
echo "  - Verify setup:     python3 verify_setup.py"
echo ""
echo "Next steps:"
echo "  1. Review data in database"
echo "  2. Implement technical indicator calculations"
echo "  3. Build backtesting framework"
echo ""