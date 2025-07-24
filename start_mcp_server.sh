#!/bin/bash

# Kroger MCP Server Startup Script
# This script starts the Kroger MCP (Model Context Protocol) server

set -e  # Exit on any error

echo "🚀 Starting Kroger MCP Server..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run 'python -m venv .venv' first."
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source .venv/bin/activate

# Check if required packages are installed
if ! python -c "import kroger_mcp" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -e .
fi

# Start the MCP server
echo "🔌 Starting MCP server on stdio..."
echo "   Use Ctrl+C to stop the server"
echo ""

python server.py