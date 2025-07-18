#!/usr/bin/env python3
"""
Startup script for the Zircuit Smart Contract LLM Agent API

This script starts the FastAPI server with proper configuration.
"""

import os
import sys
import uvicorn
from dotenv import load_dotenv

def main():
    """Start the FastAPI server"""
    # Load environment variables
    load_dotenv()
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")
    
    print(f"Starting Zircuit Smart Contract LLM Agent API")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log Level: {log_level}")
    print(f"Docs: http://{host}:{port}/docs")
    print(f"Health: http://{host}:{port}/health")
    print()
    
    # Start the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )

if __name__ == "__main__":
    main() 