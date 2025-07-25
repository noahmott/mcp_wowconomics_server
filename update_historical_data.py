#!/usr/bin/env python3
"""
Scheduled task to update historical market data
Runs market analysis to collect price data for trend tracking
"""
import asyncio
import httpx
import json
import logging
from datetime import datetime
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get server URL from environment or use default
MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/")
if "localhost" not in MCP_URL:
    # If not localhost, ensure we're using the internal Heroku URL
    MCP_URL = "http://0.0.0.0:8000/mcp/"

class MCPClient:
    def __init__(self, url: str):
        self.url = url
        self.session_id = None
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def initialize(self) -> bool:
        """Initialize MCP session"""
        try:
            response = await self.client.post(
                self.url,
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "historical-updater", "version": "1.0.0"}
                    },
                    "id": 1
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to initialize: {response.status_code}")
                return False
            
            self.session_id = response.headers.get("mcp-session-id")
            
            # Send notifications/initialized
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": self.session_id
            }
            
            await self.client.post(
                self.url,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers
            )
            
            return True
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False
    
    def _parse_sse_response(self, text: str):
        """Parse SSE response"""
        lines = text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if "result" in data:
                        result = data["result"]
                        if isinstance(result, list) and len(result) > 0:
                            content = result[0].get("content", [])
                            if content and isinstance(content[0], dict):
                                return content[0].get("text", "")
                        return str(result)
                    elif "error" in data:
                        return f"ERROR: {data['error']}"
                except:
                    pass
        return None
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a tool and return the response"""
        try:
            response = await self.client.post(
                self.url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    },
                    "id": 2
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": self.session_id
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Tool call failed: {response.status_code}")
                return None
            
            return self._parse_sse_response(response.text)
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return None
    
    async def close(self):
        await self.client.aclose()

async def update_historical_data():
    """Main function to update historical data"""
    logger.info("Starting historical data update...")
    
    # List of realms to update
    realms = [
        ("us", "stormrage"),
        ("us", "area-52"),
        ("us", "tichondrius"),
    ]
    
    client = MCPClient(MCP_URL)
    
    try:
        if not await client.initialize():
            logger.error("Failed to initialize MCP client")
            return False
        
        success_count = 0
        
        for region, realm in realms:
            logger.info(f"Updating data for {realm}-{region}...")
            
            # Run market analysis to collect historical data
            result = await client.call_tool("analyze_market_opportunities", {
                "realm_slug": realm,
                "region": region
            })
            
            if result and "Error" not in result:
                logger.info(f"Successfully updated {realm}-{region}")
                success_count += 1
            else:
                logger.error(f"Failed to update {realm}-{region}: {result[:100] if result else 'No response'}")
            
            # Small delay between realms
            await asyncio.sleep(2)
        
        # Check staging data
        staging_result = await client.call_tool("check_staging_data", {})
        if staging_result:
            logger.info("Cache status checked")
        
        logger.info(f"Historical data update completed. Success: {success_count}/{len(realms)} realms")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Update error: {e}")
        return False
    finally:
        await client.close()

def main():
    """Entry point for scheduled task"""
    start_time = datetime.now()
    logger.info(f"Historical data update started at {start_time}")
    
    try:
        # Run the async update
        success = asyncio.run(update_historical_data())
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if success:
            logger.info(f"Update completed successfully in {duration:.2f} seconds")
            sys.exit(0)
        else:
            logger.error(f"Update failed after {duration:.2f} seconds")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()