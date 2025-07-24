#!/usr/bin/env python3
"""
Start the WoW Guild MCP Server
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Start the application components"""
    
    # Load environment variables
    load_dotenv()
    
    # Check if we're in the right directory
    if not Path("app/main.py").exists():
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Check for required environment variables
    required_vars = [
        "BLIZZARD_CLIENT_ID",
        "BLIZZARD_CLIENT_SECRET", 
        "DISCORD_BOT_TOKEN",
        "OPENAI_API_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these in your .env file")
        sys.exit(1)
    
    print("Starting WoW Guild MCP Server...")
    print("=" * 50)
    
    # Start the FastAPI server
    print("Starting FastAPI MCP Server on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("MCP Tools: http://localhost:8000/mcp/tools")
    print("")
    print("To start the Discord bot, run in another terminal:")
    print("   python -m app.discord_bot")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        # Start uvicorn server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--reload", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ])
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()