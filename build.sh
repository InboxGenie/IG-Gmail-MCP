#!/bin/bash

# Remove build directory if it exists
rm -r build

# Create build directory if it doesn't exist
mkdir -p build

# Install dependencies
uv sync

# Determine OS and set appropriate lib directory case
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    LIB_DIR="lib"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    LIB_DIR="Lib"
else
    # Default to lib for other Unix-like systems
    LIB_DIR="lib"
fi

# Copy dependencies to build directory
cp -r ./.venv/$LIB_DIR/python3.13/site-packages/* build/

# Copy mcp_server directory to build directory
cp -r mcp_server build/
cp run.sh build/

cd build

zip -r ../ig-gmail-mcp-server.zip .