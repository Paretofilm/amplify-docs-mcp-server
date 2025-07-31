#!/bin/bash
# Run the AWS Amplify Documentation MCP Server

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$DIR"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install uv first."
    echo "Visit: https://github.com/astral-sh/uv"
    exit 1
fi

# Run the server with uv
echo "Starting AWS Amplify Documentation MCP Server..."
uv run python amplify_docs_server.py