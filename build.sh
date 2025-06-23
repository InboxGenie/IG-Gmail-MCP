#!/bin/bash

# Remove build directory if it exists
rm -r build

# Create build directory if it doesn't exist
mkdir -p build

# Install dependencies
uv sync

# Copy dependencies to build directory
cp -r $(realpath .venv)/Lib/site-packages/* build/

# Copy mcp_server directory to build directory
cp -r mcp_server build/

zip -r ./ig-gmail-mcp-server.zip build/