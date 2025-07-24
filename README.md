# World of Warcraft Guild Analysis MCP Server

A comprehensive AI-powered World of Warcraft guild analysis system built with FastAPI, LangGraph, and Discord integration. This application provides intelligent guild analytics, member performance tracking, and automated insights through a sophisticated MCP (Model Context Protocol) server.

## Features

- 🏰 **Comprehensive Guild Analysis** - Real-time analysis of guild performance, member activity, and raid progression
- 🤖 **AI-Powered Insights** - OpenAI integration for intelligent analysis and recommendations
- 📊 **Rich Visualizations** - Interactive charts and graphs using Plotly
- 🎮 **Discord Bot Integration** - Seamless interaction through Discord with rich embeds
- 🔄 **MCP Protocol Compliance** - Full Model Context Protocol implementation for AI assistant integration
- 📈 **Advanced Orchestration** - LangGraph state management for complex workflow handling
- ⚡ **High Performance** - Redis caching and optimized database queries
- 🛡️ **Production Ready** - Comprehensive error handling and monitoring

## Architecture

```
Discord Bot ←→ FastAPI MCP Server ←→ LangGraph Orchestrator
                      ↓
              Blizzard Battle.net API
                      ↓
              PostgreSQL + Redis Cache
                      ↓
              Plotly Visualizations
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Redis server
- Blizzard Battle.net API credentials
- Discord bot token
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/wow-guild-mcp.git
   cd wow-guild-mcp
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Initialize the database**
   ```bash
   python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"
   ```

5. **Run the application**
   ```bash
   # Start the web server
   uvicorn app.main:app --reload

   # Start the Discord bot (in another terminal)
   python -m app.discord_bot
   ```

## API Documentation

### MCP Tools

#### `analyze_guild_performance`
Analyze guild performance metrics and member activity.

**Parameters:**
- `realm` (str): Server realm (e.g., 'stormrage', 'area-52')
- `guild_name` (str): Guild name
- `analysis_type` (str, optional): Type of analysis ('comprehensive', 'basic', 'performance')

#### `generate_raid_progress_chart`
Generate visual raid progression charts.

**Parameters:**
- `realm` (str): Server realm
- `guild_name` (str): Guild name
- `raid_tier` (str, optional): Raid tier ('current', 'dragonflight', 'shadowlands')

#### `compare_member_performance`
Compare performance metrics across guild members.

**Parameters:**
- `realm` (str): Server realm
- `guild_name` (str): Guild name
- `member_names` (list[str]): List of character names to compare
- `metric` (str, optional): Metric to compare ('item_level', 'achievement_points', 'guild_rank')

## Discord Bot Commands

### Guild Commands
- `!wow guild <realm> <guild_name>` - Comprehensive guild analysis
- `!wow members <realm> <guild_name>` - Guild member list
- `!wow progress <realm> <guild_name>` - Raid progression

### Member Commands
- `!wow member <realm> <character_name>` - Individual member analysis
- `!wow compare <realm> <guild_name> <member1> <member2>...` - Compare members

### Chart Commands
- `!wow chart <realm> <guild_name>` - Generate guild charts
- `!wow classes <realm> <guild_name>` - Class distribution chart

## Deployment

### Heroku Deployment

1. **Create Heroku app**
   ```bash
   heroku create wow-guild-mcp-server
   ```

2. **Add required add-ons**
   ```bash
   heroku addons:create heroku-postgresql:mini
   heroku addons:create heroku-redis:mini
   heroku addons:create papertrail:choklad
   ```

3. **Set environment variables**
   ```bash
   heroku config:set BLIZZARD_CLIENT_ID=your_client_id
   heroku config:set BLIZZARD_CLIENT_SECRET=your_client_secret
   heroku config:set DISCORD_BOT_TOKEN=your_bot_token
   heroku config:set OPENAI_API_KEY=your_openai_key
   ```

4. **Deploy**
   ```bash
   git push heroku main
   heroku ps:scale web=1 bot=1
   ```

### Docker Deployment

```bash
# Build the image
docker build -t wow-guild-mcp .

# Run the container
docker run -p 8000:8000 --env-file .env wow-guild-mcp
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BLIZZARD_CLIENT_ID` | Blizzard Battle.net API Client ID | Yes |
| `BLIZZARD_CLIENT_SECRET` | Blizzard Battle.net API Client Secret | Yes |
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes |
| `OPENAI_API_KEY` | OpenAI API key for AI insights | Yes |
| `DATABASE_URL` | PostgreSQL database URL | Yes |
| `REDIS_URL` | Redis server URL | Yes |
| `LANGSMITH_API_KEY` | LangSmith API key (optional) | No |
| `DEBUG` | Enable debug mode | No |

### API Rate Limits

The application implements intelligent rate limiting for the Blizzard API:
- **Default**: 100 requests per second
- **Automatic backoff** on rate limit responses
- **Caching** to reduce API calls

## Development

### Project Structure

```
app/
├── __init__.py
├── main.py                 # FastAPI application
├── mcp_server.py          # MCP implementation
├── discord_bot.py         # Discord bot client
├── api/
│   └── blizzard_client.py # WoW API integration
├── models/
│   ├── database.py        # Database configuration
│   ├── guild.py          # Guild models
│   ├── member.py         # Member models
│   └── raid.py           # Raid models
├── workflows/
│   └── guild_analysis.py # LangGraph workflows
├── visualization/
│   └── chart_generator.py # Chart generation
└── utils/
    ├── cache.py          # Redis caching
    └── errors.py         # Error handling
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black app/

# Sort imports
isort app/

# Type checking
mypy app/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 **Documentation**: Check this README and code comments
- 🐛 **Bug Reports**: Open an issue on GitHub
- 💬 **Questions**: Start a discussion on GitHub
- 📧 **Contact**: [your-email@example.com]

## Acknowledgments

- Blizzard Entertainment for the Battle.net API
- OpenAI for AI capabilities
- Discord for bot integration platform
- The Python community for excellent libraries