# MCP Server Usage Guide

## Server Details

- **Production URL**: https://wow-guild-mcp-server-7f17b3f6ea0a.herokuapp.com/mcp/
- **Local URL**: http://localhost:8000/mcp/
- **Transport**: FastMCP 2.0 HTTP with Server-Sent Events (SSE)

## Available Tools (10 total)

1. **analyze_market_opportunities** - Find profitable market opportunities on a realm
2. **analyze_crafting_profits** - Analyze crafting profitability 
3. **predict_market_trends** - Predict market trends based on historical data
4. **get_historical_data** - Get historical price data for items
5. **update_historical_database** - Update the historical database
6. **analyze_with_details** - Detailed market analysis with step-by-step calculations
7. **debug_api_data** - Debug API responses and data
8. **get_item_info** - Get detailed information about WoW items
9. **check_staging_data** - Check staging data cache statistics
10. **get_analysis_help** - Get help on using the analysis tools

## Connection Requirements

FastMCP 2.0 HTTP transport requires:
- Headers: `Accept: application/json, text/event-stream`
- Session management via cookies or session ID
- Support for Server-Sent Events (SSE)

## Testing the Server

### Local Testing
```bash
# Start the server locally
python analysis_mcp_server.py

# The server will run on http://localhost:8000/mcp/
```

### Production Testing
The server is deployed on Heroku and responds to MCP protocol requests at the `/mcp/` endpoint.

## Integration with Claude Desktop

To use with Claude Desktop or other MCP clients, configure the connection to use the HTTP transport with the production URL.

## Troubleshooting

1. **404 Not Found on root**: This is expected. The server only serves the `/mcp/` endpoint.
2. **406 Not Acceptable**: Ensure your client accepts both `application/json` and `text/event-stream`.
3. **400 Missing Session ID**: FastMCP HTTP transport requires session management.

## Development Notes

- The server uses FastMCP 2.0 with HTTP transport
- All tools are properly registered and working
- The server integrates with Blizzard's WoW API for real-time data
- Historical data is stored for trend analysis