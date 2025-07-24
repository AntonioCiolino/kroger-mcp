#!/bin/bash

# Kroger Web App Startup Script
# This script starts the Flask web application for the Kroger MCP tools

set -e  # Exit on any error

echo "🌐 Starting Kroger Web App..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run 'python -m venv .venv' first."
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source .venv/bin/activate

# Check if required packages are installed
if ! python -c "import flask" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
fi

# Set Flask environment variables
export FLASK_APP=web_ui.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Start the web application
echo "🚀 Starting Flask web app..."
echo "   Web interface will be available at: http://localhost:5000"
echo "   Use Ctrl+C to stop the server"
echo ""

python web_ui.py