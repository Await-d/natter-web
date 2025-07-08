# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Natter Web管理工具 is a web-based management interface for the Natter network tunneling tool. It provides a graphical interface to manage multiple Natter service instances, monitor their status, and receive notifications through IYUU push services.

## Key Architecture Components

### Backend (Python HTTP Server)
- **Main Server**: `web/server.py` - Single-file HTTP server handling all API endpoints and static file serving
- **Process Management**: Uses `psutil` library to manage Natter subprocess instances
- **Data Persistence**: JSON files stored in `web/data/` directory for configuration and state
- **Message Queue System**: Batch processing for IYUU push notifications with configurable intervals
- **Authentication**: Token-based authentication with admin/guest role separation

### Frontend (Vanilla HTML/CSS/JS)
- **Unified Login**: `web/login.html` - Single entry point for both admin and guest users
- **Admin Interface**: `web/index.html` - Full management capabilities
- **Guest Interface**: `web/guest.html` - Read-only access with service group filtering
- **No External Dependencies**: All styles and scripts are self-contained

### Data Storage Structure
```
web/data/
├── services.json        # Active service instances and their configurations
├── service_groups.json  # Guest access groups and permissions
├── templates.json       # Saved configuration templates
└── iyuu_config.json    # Push notification settings
```

### Natter Integration
- **Core Tool**: `natter/natter.py` - The actual network tunneling tool being managed
- **Process Wrapper**: `NatterService` class captures stdout, parses status, and manages lifecycle
- **Address Parsing**: Regex patterns extract mapped addresses, NAT types, and port status from Natter output

## Common Commands

### Development
```bash
# Start server locally (from web/ directory)
python3 server.py [port]

# Test server module import
python3 -c "import server; print('✅ Server module imported successfully')"

# Check dependencies
pip3 list | grep -E "(psutil|requests)"
```

### Docker Deployment
```bash
# Build and run with docker-compose
docker-compose up -d

# Build Docker image manually
docker build -t natter-web .

# Run with custom port and data persistence
docker run -d --name natter-web \
  --network host \
  --cap-add NET_ADMIN \
  -v "$(pwd)/data:/app/data" \
  -e WEB_PORT=8080 \
  -e ADMIN_PASSWORD=your_password \
  natter-web
```

### Git Operations
```bash
# Push to all configured remote repositories
./push_all.sh

# Current remotes: origin (GitHub), new-gogs, test-repo
```

## Configuration Management

### Environment Variables
- `NATTER_PATH`: Path to natter.py (default: ../natter/natter.py)
- `DATA_DIR`: Data storage directory (default: ./data)
- `ADMIN_PASSWORD`: Admin authentication (default: "zd2580")
- `WEB_PORT`: HTTP server port (default: 8080)
- `GUEST_ENABLED`: Enable guest system (default: true)
- `IYUU_ENABLED`: Enable push notifications (default: true)

### Key Configuration Files
- **docker-compose.yml**: Complete container setup with network and volume configuration
- **start.sh**: Container initialization script with dependency checks and system setup
- **Dockerfile**: Multi-stage build with Python dependencies and system tools

## Service Management Architecture

### Service Lifecycle
1. **Creation**: User input → validation → NatterService instance → subprocess spawn
2. **Monitoring**: Background thread captures stdout → parses status → updates service state
3. **Notification**: Status changes → message queue → batch processing → IYUU push
4. **Termination**: Graceful shutdown → process cleanup → status update

### Message Queue System
- **Batching**: Multiple events within 5-60 seconds are consolidated
- **Categories**: Different message types (启动/停止/错误/地址变更/定时报告)
- **Deduplication**: Prevents spam for scheduled reports and repeated events
- **Rate Limiting**: Minimum 5-minute interval between push batches

### Authentication Flow
- **Unified Login**: Single login.html endpoint for all user types
- **Token Management**: Session tokens with 24-hour expiration
- **Role Detection**: Password determines admin vs guest access level
- **Group Permissions**: Guests see only services in their assigned groups

## Testing and Quality Assurance

### Local Testing
```bash
# Basic functionality test
python3 -c "import server; print('Server module loads correctly')"

# Start test server and verify endpoints
python3 server.py 8081 &
curl -s http://localhost:8081/api/version
curl -s http://localhost:8081/ | grep -o "<title>.*</title>"
pkill -f "python3 server.py"
```

### Docker Testing
```bash
# Test container build
docker build -t natter-web-test .

# Verify container startup
docker run --rm natter-web-test python3 /app/web/server.py --help
```

## Critical Implementation Details

### Natter Process Integration
- **Output Parsing**: Real-time regex parsing of Natter's stdout for status extraction
- **Address Detection**: Supports both legacy and v2.1.1 format address parsing
- **Error Handling**: Detects common issues (nftables unavailable, pcap failures) and provides user guidance
- **Resource Management**: Automatic cleanup of zombie processes and memory leak prevention

### Security Considerations
- **No External Dependencies**: Frontend uses only vanilla JS/CSS to avoid supply chain risks
- **Input Validation**: All user inputs are validated before subprocess execution
- **Process Isolation**: Each Natter instance runs as separate subprocess with controlled arguments
- **File System Access**: Restricted to designated data directory

### Performance Optimizations
- **Message Batching**: Reduces notification spam through intelligent queuing
- **Process Monitoring**: Efficient polling using psutil for minimal CPU overhead
- **Log Rotation**: Automatic truncation of service output logs to prevent memory bloat
- **Thread Management**: Daemon threads for background tasks with proper lifecycle management