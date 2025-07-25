"""
Minimal test server to debug FastMCP 2.10.6
"""
import os
import logging
from fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create minimal server
mcp = FastMCP("Minimal Test Server")

@mcp.tool()
def hello(name: str = "World") -> str:
    """Say hello to someone"""
    return f"Hello, {name}!"

@mcp.tool()
async def add_numbers(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

def main():
    """Run the server"""
    port = int(os.getenv("PORT", "8006"))
    
    logger.info(f"Starting Minimal Test Server on port {port}")
    logger.info(f"FastMCP version: {__import__('fastmcp').__version__}")
    
    # Run with different transports to test
    transport = os.getenv("TRANSPORT", "http")
    logger.info(f"Using transport: {transport}")
    
    mcp.run(
        transport=transport,
        host="0.0.0.0",
        port=port
    )

if __name__ == "__main__":
    main()