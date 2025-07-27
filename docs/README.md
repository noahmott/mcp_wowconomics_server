# WoW Guild Analytics Documentation

Welcome to the comprehensive documentation for the WoW Guild Analytics project.

## Documentation Structure

### 📁 [Architecture](./architecture/)
- [DESIGN_DOCUMENT.md](./architecture/DESIGN_DOCUMENT.md) - System design and architecture overview
- Technical decisions and patterns used

### 📁 [API Documentation](./api/)
- [MCP_USAGE.md](./api/MCP_USAGE.md) - Model Context Protocol (MCP) server usage guide
- [MCP_ENDPOINT_TEST_RESULTS.md](./MCP_ENDPOINT_TEST_RESULTS.md) - MCP endpoint testing results
- API endpoints and integration guides

### 📁 [Development](./development/)
- [PEP8_COMPLIANCE.md](./development/PEP8_COMPLIANCE.md) - Code quality and PEP 8 compliance report
- [FILE_ORGANIZATION.md](./development/FILE_ORGANIZATION.md) - Repository structure analysis
- [REORGANIZATION_PLAN.md](./development/REORGANIZATION_PLAN.md) - File organization improvement plan
- Development setup and guidelines

### 📁 [Deployment](./deployment/)
- Docker deployment guides
- Heroku deployment instructions
- Environment configuration

### 📁 [Historical](.)
- [CLASSIC_API_NOTES.md](./CLASSIC_API_NOTES.md) - Classic WoW API implementation notes
- [PERSISTENCE_TEST_RESULTS.md](./PERSISTENCE_TEST_RESULTS.md) - Database persistence testing

## Quick Links

### Getting Started
1. [Development Setup](./development/SETUP_GUIDE.md)
2. [MCP Usage Guide](./api/MCP_USAGE.md)
3. [Architecture Overview](./architecture/DESIGN_DOCUMENT.md)

### For Developers
- [Code Standards](./development/PEP8_COMPLIANCE.md)
- [Repository Structure](./development/FILE_ORGANIZATION.md)
- [API Documentation](./api/)

### For Operations
- [Docker Deployment](./deployment/DOCKER_GUIDE.md)
- [Environment Configuration](../README.md#configuration)
- [Monitoring and Logs](./deployment/MONITORING.md)

## Project Overview

WoW Guild Analytics is a comprehensive tool for analyzing World of Warcraft guild data, providing:
- Real-time guild member analysis
- Performance metrics and insights
- MCP server integration for Claude AI
- Support for both Classic and Retail WoW

## Key Features

- **FastMCP Integration**: Full Model Context Protocol support
- **Modular Architecture**: Clean separation of concerns with DDD principles
- **Performance Optimized**: Handles large guilds (1000+ members) efficiently
- **Multi-Version Support**: Works with both Classic and Retail WoW APIs
- **Comprehensive Analytics**: Deep insights into guild performance

## Documentation Standards

All documentation follows these standards:
- Markdown format with clear headings
- Code examples where applicable
- Updated with each major change
- Version-specific notes when needed

## Contributing

When adding new documentation:
1. Place it in the appropriate subdirectory
2. Update this index file
3. Follow the existing format and style
4. Include practical examples

## Need Help?

- Check the [FAQ](./FAQ.md)
- Review [Common Issues](./TROUBLESHOOTING.md)
- Open an issue on GitHub