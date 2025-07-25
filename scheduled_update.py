#!/usr/bin/env python3
"""
Heroku Scheduler task to update historical market data
This script is designed to be run by Heroku Scheduler add-on
"""
import asyncio
import httpx
import json
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the app URL from Heroku environment
APP_URL = os.getenv("APP_URL", "https://wow-guild-mcp-server-7f17b3f6ea0a.herokuapp.com")
MCP_ENDPOINT = f"{APP_URL}/mcp/"

async def update_historical_data():
    """Update historical data using the MCP server's update tool"""
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            # Initialize MCP session
            logger.info(f"Connecting to MCP server at {MCP_ENDPOINT}")
            
            init_response = await client.post(
                MCP_ENDPOINT,
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "scheduler", "version": "1.0.0"}
                    },
                    "id": 1
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            if init_response.status_code != 200:
                logger.error(f"Failed to initialize: {init_response.status_code}")
                return False
            
            session_id = init_response.headers.get("mcp-session-id")
            
            # Send notifications/initialized
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": session_id
            }
            
            await client.post(
                MCP_ENDPOINT,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers
            )
            
            # Call update_historical_database tool
            logger.info("Calling update_historical_database tool...")
            
            update_response = await client.post(
                MCP_ENDPOINT,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "update_historical_database",
                        "arguments": {
                            "realms": "popular",  # Update popular realms
                            "top_items": 200     # Track more items
                        }
                    },
                    "id": 2
                },
                headers=headers
            )
            
            if update_response.status_code == 200:
                # Parse SSE response
                lines = update_response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            if "result" in data:
                                result = data["result"]
                                if isinstance(result, list) and len(result) > 0:
                                    content = result[0].get("content", [])
                                    if content and isinstance(content[0], dict):
                                        result_text = content[0].get("text", "")
                                        logger.info("Update result received")
                                        # Log key metrics
                                        if "Realms Updated:" in result_text:
                                            for line in result_text.split('\n'):
                                                if any(keyword in line for keyword in ["Realms Updated:", "Total Items Tracked:", "Data Saved:"]):
                                                    logger.info(line.strip())
                                        return True
                        except Exception as e:
                            logger.error(f"Error parsing response: {e}")
                
                logger.info("Update completed")
                return True
            else:
                logger.error(f"Update failed: {update_response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error during update: {e}")
            return False

def main():
    """Main entry point for Heroku Scheduler"""
    start_time = datetime.now()
    logger.info(f"=== Historical Data Update Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    try:
        # Run the update
        success = asyncio.run(update_historical_data())
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if success:
            logger.info(f"✓ Update completed successfully in {duration:.1f} seconds")
        else:
            logger.error(f"✗ Update failed after {duration:.1f} seconds")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    
    logger.info("=== Update Task Finished ===")

if __name__ == "__main__":
    main()