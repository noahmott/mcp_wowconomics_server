#!/usr/bin/env python3
"""
Start the Discord Bot
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Start the Discord bot"""
    
    # Load environment variables
    load_dotenv()
    
    # Check if we're in the right directory
    if not Path("app/discord_bot.py").exists():
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Check for Discord bot token
    if not os.getenv("DISCORD_BOT_TOKEN"):
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        print("Please set this in your .env file")
        sys.exit(1)
    
    # Check for MCP server URL
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
    
    print("Starting WoW Guild Discord Bot...")
    print("=" * 50)
    print(f"MCP Server: {mcp_server_url}")
    print("Bot Commands:")
    print("   !wow wowhelp           - Show help")
    print("   !wow guild <realm> <guild_name>  - Analyze guild")
    print("   !wow member <realm> <character>  - Analyze character")
    print("   !wow compare <realm> <guild> <member1> <member2>...")
    print("")
    print("Make sure the MCP server is running first!")
    print("Press Ctrl+C to stop the bot")
    print("=" * 50)
    
    try:
        # Start the Discord bot
        from app.discord_bot import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()