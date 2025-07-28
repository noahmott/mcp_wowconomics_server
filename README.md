# ⚔️ WoW Guild Analytics MCP Server

![World of Warcraft](https://img.shields.io/badge/World%20of%20Warcraft-Retail%20%26%20Classic-f4c430?style=for-the-badge&logo=battle.net&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Caching-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688?style=for-the-badge&logo=fastapi&logoColor=white)

A powerful Model Context Protocol (MCP) server that provides AI assistants with comprehensive World of Warcraft guild analytics, member performance tracking, auction house monitoring, and data visualization capabilities. Built with FastMCP 2.0 and optimized for high performance with Redis caching and modular architecture.

## Features

### 🛡️ Guild Management Tools ![Paladin](https://img.shields.io/badge/-Paladin-F58CBA?style=flat-square)
- **Guild Performance Analysis** - Comprehensive guild metrics with AI-powered insights
- **Member List Management** - Detailed roster with sorting and filtering options
- **Raid Progress Tracking** - Visual raid progression charts and statistics
- **Member Performance Comparison** - Compare metrics across guild members

### 💰 Economy & Auction House ![Rogue](https://img.shields.io/badge/-Rogue-FFF569?style=flat-square)
- **Real-time Auction Snapshots** - Current market data with price aggregation
- **Economy Trend Analysis** - Historical price tracking up to 30 days
- **Market Opportunity Scanner** - Find profitable items with customizable margins
- **Item Market History** - Detailed analysis of specific item trends

### 🧙 Character Analytics ![Mage](https://img.shields.io/badge/-Mage-69CCF0?style=flat-square)
- **Member Performance Analysis** - Individual character progression tracking
- **Character Details Lookup** - Comprehensive character information including:
  - Equipment and item levels
  - Specializations and talents
  - Achievements and statistics
  - PvP ratings and rankings
  - Mythic+ scores
  - Collections and titles

### 🌍 Realm & Server Tools ![Shaman](https://img.shields.io/badge/-Shaman-0070DE?style=flat-square)
- **Realm Status Monitoring** - Server status and population data
- **Connected Realm Lookup** - Find connected realm IDs for API calls
- **Classic Realm Support** - Full support for Classic progression servers

### 📊 Data Visualization ![Priest](https://img.shields.io/badge/-Priest-FFFFFF?style=flat-square)
- **Raid Progress Charts** - Visual representation of guild raid completion
- **Performance Comparison Graphs** - Side-by-side member metric comparison
- **Market Trend Visualizations** - Price history charts and analysis

### 🔧 Diagnostic & Testing ![Hunter](https://img.shields.io/badge/-Hunter-ABD473?style=flat-square)
- **API Connection Testing** - Verify Blizzard API connectivity
- **Classic Auction House Testing** - Test Classic realm auction data
- **Supabase Connection Verification** - Database connectivity checks

## Technical Architecture

### Core Technologies
- **FastMCP 2.0+** - Model Context Protocol implementation
- **FastAPI** - Modern async web framework
- **Redis 6.2** - High-performance caching layer
- **SQLAlchemy 2.0** - Async database ORM
- **Supabase** - Cloud database with real-time features

### Performance Optimizations
- **Intelligent Redis Caching** - Reduces API calls significantly
- **15-Day Guild Roster Cache** - Long-term caching for stable data
- **Hourly Economy Snapshots** - Balanced freshness vs. API limits
- **Async/Await Throughout** - Non-blocking I/O operations
- **Modular Tool Design** - 82% code reduction through refactoring

### AI Integration
- **OpenAI GPT-4o-mini** - Intelligent analysis and insights
- **LangChain/LangGraph** - Sophisticated workflow orchestration
- **Context-Aware Analysis** - Tailored insights based on data patterns

## Quick Start

### Prerequisites
- Python 3.9+
- Redis server (local or cloud)
- Blizzard API credentials
- (Optional) Supabase account
- (Optional) OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd guilddiscordbot
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Required Environment Variables

```env
# Blizzard API (Required)
BLIZZARD_CLIENT_ID=your_client_id
BLIZZARD_CLIENT_SECRET=your_client_secret

# Redis (Required for caching)
REDIS_URL=redis://localhost:6379  # Or your Heroku Redis URL

# OpenAI (Optional - for AI analysis)
OPENAI_API_KEY=your_openai_key

# Supabase (Optional - for activity logging)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### Running the Server

#### Development Mode
```bash
python -m app.mcp_server_fastmcp
```

#### Production Mode (with Gunicorn)
```bash
gunicorn app.mcp_server_fastmcp:app -w 4 -k uvicorn.workers.UvicornWorker
```

#### Docker Compose (Recommended)
```bash
docker-compose -f config/docker/docker-compose.yml up
```

## Usage with AI Assistants

### Claude Desktop Integration

1. Add to Claude Desktop configuration:
```json
{
  "mcpServers": {
    "wow-guild": {
      "command": "python",
      "args": ["-m", "app.mcp_server_fastmcp"],
      "cwd": "/path/to/guilddiscordbot",
      "env": {
        "BLIZZARD_CLIENT_ID": "your_client_id",
        "BLIZZARD_CLIENT_SECRET": "your_client_secret",
        "REDIS_URL": "redis://localhost:6379"
      }
    }
  }
}
```

2. Restart Claude Desktop to load the MCP server

### Example Queries

```text
"Analyze the performance of guild Elevate on Stormrage"

"Show me the current auction house prices for Flask of Power on Mankrik Classic"

"Compare the item levels of the top 5 DPS members in Method on Tarren Mill"

"Find market opportunities on Area-52 with at least 50% profit margin"

"Generate a raid progress chart for Liquid on Illidan"
```

## Available MCP Tools

### Guild Tools
- `analyze_guild_performance` - Comprehensive guild analysis with AI insights
- `get_guild_member_list` - Retrieve and sort guild roster

### Member Tools  
- `analyze_member_performance` - Individual character performance metrics
- `get_character_details` - Full character profile data

### Auction Tools
- `get_auction_house_snapshot` - Current market prices
- `capture_economy_snapshot` - Store hourly market data
- `get_economy_trends` - Historical price analysis
- `find_market_opportunities` - Profitable item scanner
- `analyze_item_market_history` - Single item trend analysis

### Item Tools
- `lookup_item_details` - Single item information
- `lookup_multiple_items` - Batch item lookups

### Realm Tools
- `get_realm_status` - Server status and info
- `get_classic_realm_id` - Classic realm ID lookup

### Visualization Tools
- `generate_raid_progress_chart` - Raid completion visuals
- `compare_member_performance` - Member metric comparison

### Diagnostic Tools
- `test_classic_auction_house` - Classic AH connectivity
- `test_supabase_connection` - Database connection test

## Development

### Project Structure
```
guilddiscordbot/
├── app/
│   ├── core/           # Core infrastructure
│   ├── tools/          # MCP tool implementations
│   ├── services/       # Business logic
│   ├── models/         # Database models
│   ├── api/            # External API clients
│   ├── workflows/      # Complex operations
│   └── utils/          # Utility functions
├── tests/              # Test suite
├── config/             # Configuration files
├── docs/               # Documentation
└── deployment/         # Deployment configs
```

### Running Tests
```bash
# Quick tool tests
python tests/quick_test_tools.py

# Comprehensive test suite
python tests/test_refactored_tools.py

# Test specific tool category
python tests/quick_test_tools.py guild
python tests/quick_test_tools.py auction
```

### Adding New Tools

1. Create tool function in appropriate module:
```python
# app/tools/your_tools.py
from .base import mcp_tool, with_supabase_logging

@mcp_tool()
@with_supabase_logging
async def your_new_tool(param1: str, param2: int = 10) -> Dict[str, Any]:
    """Tool description for MCP"""
    # Implementation
    return {"result": "data"}
```

2. Import in main server file:
```python
# app/mcp_server_fastmcp.py
from app.tools.your_tools import your_new_tool
```

3. Test your tool:
```bash
python tests/quick_test_tools.py
```

## Deployment

### Heroku Deployment

1. Create Heroku app:
```bash
heroku create your-app-name
```

2. Add Redis addon:
```bash
heroku addons:create heroku-redis:hobby-dev
```

3. Set environment variables:
```bash
heroku config:set BLIZZARD_CLIENT_ID=your_id
heroku config:set BLIZZARD_CLIENT_SECRET=your_secret
```

4. Deploy:
```bash
git push heroku main
```

### Docker Deployment

Build and run with Docker:
```bash
docker build -f config/docker/Dockerfile -t wow-guild-mcp .
docker run -p 8000:8000 --env-file .env wow-guild-mcp
```

## Performance Considerations

### Caching Strategy
- **Guild Roster**: 15-day cache (from constants.py)
- **Auction Data**: 1-hour cache for market freshness
- **Character Data**: 2-hour cache (from redis_staging.py)
- **Guild Info**: 6-hour cache (from redis_staging.py)
- **Realm Data**: 24-hour cache (from redis_staging.py)

### API Rate Limits
- Blizzard API: 36,000 requests/hour
- Efficient batching and caching minimize API usage
- Automatic retry with exponential backoff

### Resource Usage
- Redis memory: 256MB max (configured in docker-compose.yml)
- CPU: Minimal, mostly I/O bound

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all functions
- Add docstrings to all public functions
- Write tests for new features

## Troubleshooting

### Common Issues

**Redis Connection Failed**
- Ensure Redis server is running
- Check REDIS_URL format: `redis://user:password@host:port`
- For Heroku, URL is automatically set

**Blizzard API Errors**
- Verify API credentials are correct
- Check realm name spelling (e.g., 'area-52' not 'area 52')
- Ensure proper game_version ('retail' or 'classic')

**Character Not Found**
- Character name is case-sensitive
- Ensure realm name is correct
- Character must exist and be recently active

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Acknowledgments

- Built with [FastMCP 2.0](https://github.com/jlowin/fastmcp) - Fast Model Context Protocol implementation
- Powered by [Blizzard Entertainment API](https://develop.battle.net/)
- Inspired by community projects:
  - [WoWthing](https://github.com/ThingEngineering/wowthing-again) - Web tool for WoW character management with Redis job scheduling
  - [Guild Roster Manager](https://github.com/TheGeneticsGuy/Guild-Roster-Manager) - In-game addon for guild management and data syncing
  - [Raider.IO](https://raider.io) - Performance tracking with high-volume caching patterns

### Open Source WoW Icons

For projects needing World of Warcraft icons, these open source repositories are available:

- [Wow-Icons](https://github.com/orourkek/Wow-Icons) - Collection of WoW icons including class icons, specializations, and boss models
- [Clean Icons - Mechagnome Edition](https://github.com/AcidWeb/Clean-Icons-Mechagnome-Edition) - Upscaled icon pack for World of Warcraft
- [wow_icons](https://github.com/Znuff/wow_icons) - Tools and scripts to convert WoW icons to a uniform look
- [IconPacks](https://github.com/kodewdle/IconPacks) - Styled icon packs for World of Warcraft
- [wowspecsemojis](https://github.com/danetch/wowspecsemojis) - WoW specialization icons as Discord emojis

Note: For official WoW media assets, use [Blizzard's Media API](https://develop.battle.net/documentation/world-of-warcraft/guides/media-documents) with proper attribution.

## Support

For questions or support, please email: noah.mott1@gmail.com

---

*Last updated: July 2025*

![Built with Claude](https://img.shields.io/badge/Built%20with-Claude-orange?style=for-the-badge)

*Coding assisted by Claude*