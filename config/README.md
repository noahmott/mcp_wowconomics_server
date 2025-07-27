# Configuration Directory

This directory contains all configuration files for the WoW Guild Analytics project.

## Structure

- **docker/** - Docker-related configuration
  - `Dockerfile` - Main Docker image configuration
  - `docker-compose.yml` - Docker Compose orchestration
  - `entrypoint.sh` - Docker container entrypoint script

- **settings/** - Application settings (future)
  - Will contain environment-specific settings

## Usage

### Docker

To build and run with Docker Compose:
```bash
cd config/docker
docker-compose up --build
```

Or from project root:
```bash
docker-compose -f config/docker/docker-compose.yml up --build
```

### Environment Variables

Copy `.env.example` from project root and configure:
```bash
cp .env.example .env
# Edit .env with your credentials
```