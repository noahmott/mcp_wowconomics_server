# WoW Economic Analysis MCP Server

A powerful Model Context Protocol (MCP) server for World of Warcraft economic analysis, providing real-time market insights, crafting profitability calculations, and trend predictions.

## Features

- 📊 **Market Analysis** - Real-time analysis of WoW auction house data across realms
- 💰 **Crafting Profits** - Calculate profitability for crafting professions
- 📈 **Trend Prediction** - Historical data tracking and market trend analysis
- 🔍 **Item Intelligence** - Detailed item information and market positioning
- 🤖 **AI Integration** - MCP protocol for seamless AI assistant integration
- ⚡ **High Performance** - Redis caching and optimized API calls
- 🌐 **Multi-Region Support** - Works with US, EU, KR, and TW regions

## Available MCP Tools

1. **analyze_market_opportunities** - Find profitable market opportunities on a realm
2. **analyze_crafting_profits** - Analyze crafting profitability for recipes
3. **predict_market_trends** - Predict market trends based on historical data
4. **get_historical_data** - Retrieve historical price data for items
5. **update_historical_database** - Update the historical database
6. **analyze_with_details** - Detailed market analysis with calculations
7. **debug_api_data** - Debug API responses and data
8. **get_item_info** - Get detailed information about WoW items
9. **check_staging_data** - Check staging data cache statistics
10. **get_analysis_help** - Get help on using the analysis tools

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (for data persistence)
- Redis server (for caching)
- Blizzard Battle.net API credentials

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/wow-economic-mcp.git
   cd wow-economic-mcp
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys:
   # - BLIZZARD_CLIENT_ID
   # - BLIZZARD_CLIENT_SECRET
   # - DATABASE_URL (optional)
   # - REDIS_URL (optional)
   ```

4. **Run the MCP server**
   ```bash
   python analysis_mcp_server.py
   ```

   The server will start on `http://localhost:8000/mcp/`

## Usage Examples

### Finding Market Opportunities
```python
# The MCP server will analyze current market conditions
# and identify items with high profit potential
analyze_market_opportunities(realm_slug="stormrage", region="us")
```

### Checking Crafting Profitability
```python
# Analyze which crafting recipes are currently profitable
analyze_crafting_profits(
    profession="alchemy",
    realm_slug="area-52",
    region="us",
    min_profit=1000
)
```

### Item Information Lookup
```python
# Get detailed information about any WoW item
get_item_info(item_name="Flask of Tempered Versatility")
```

## Deployment

### Heroku Deployment

The project includes configuration for Heroku deployment:

1. **Create Heroku app**
   ```bash
   heroku create your-app-name
   ```

2. **Set environment variables**
   ```bash
   heroku config:set BLIZZARD_CLIENT_ID=your_client_id
   heroku config:set BLIZZARD_CLIENT_SECRET=your_client_secret
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

### Docker Deployment

```bash
# Build the image
docker build -t wow-economic-mcp .

# Run the container
docker run -p 8000:8000 --env-file .env wow-economic-mcp
```

## Architecture

```
MCP Client (Claude, etc.) ←→ FastMCP Server
                                    ↓
                            Blizzard WoW API
                                    ↓
                            Data Processing Layer
                                    ↓
                        PostgreSQL + Redis Cache
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BLIZZARD_CLIENT_ID` | Blizzard API Client ID | Yes |
| `BLIZZARD_CLIENT_SECRET` | Blizzard API Client Secret | Yes |
| `DATABASE_URL` | PostgreSQL connection string | No |
| `REDIS_URL` | Redis connection string | No |
| `PORT` | Server port (default: 8000) | No |

### API Rate Limiting

The server implements intelligent rate limiting:
- Respects Blizzard API rate limits
- Implements caching to reduce API calls
- Automatic retry with exponential backoff

## Development

### Project Structure

```
├── analysis_mcp_server.py    # Main MCP server
├── app/
│   ├── api/
│   │   └── blizzard_client.py    # WoW API client
│   ├── models/
│   │   ├── database.py           # Database models
│   │   └── wow_cache.py          # Cache models
│   └── services/
│       └── wow_data_staging.py   # Data staging service
├── scheduled_update.py           # Scheduled data updates
└── requirements.txt              # Python dependencies
```

### Running Tests

```bash
# Run the MCP server locally
python analysis_mcp_server.py

# Test with FastMCP client
python -c "from fastmcp import Client; ..."
```

## MCP Integration

This server implements the Model Context Protocol (MCP) using FastMCP 2.0, making it compatible with:
- Claude Desktop
- Other MCP-compatible AI assistants
- Custom MCP clients

For integration details, see [MCP Usage Guide](README_MCP_USAGE.md).

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-analysis`)
3. Commit your changes (`git commit -m 'Add new analysis tool'`)
4. Push to the branch (`git push origin feature/new-analysis`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Blizzard Entertainment for the Battle.net API
- FastMCP for the excellent MCP implementation
- The WoW community for market insights