#!/bin/bash
# RFBooking FastAPI OSS - Management Script
# Copyright (C) 2025 Oleg Tokmakov
# SPDX-License-Identifier: AGPL-3.0-or-later

set -e

CONTAINER_NAME="rfbooking"
CONFIG_DIR="./config"
DATA_DIR="./data"
DEFAULT_PORT="8000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  RFBooking FastAPI OSS - Management${NC}"
    echo -e "${BLUE}============================================${NC}"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
}

check_container_running() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_error "Container '${CONTAINER_NAME}' is not running"
        echo "Start it with: docker-compose up -d"
        exit 1
    fi
}

# Detect the host's LAN IP address
detect_lan_ip() {
    local ip=""

    # Method 1: Linux - get IP from default route interface
    if command -v ip &> /dev/null; then
        local iface=$(ip route | grep default | awk '{print $5}' | head -1)
        if [ -n "$iface" ]; then
            ip=$(ip -4 addr show "$iface" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)
        fi
    fi

    # Method 2: hostname -I (Linux)
    if [ -z "$ip" ] && command -v hostname &> /dev/null; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi

    # Method 3: macOS - get IP from en0 or en1
    if [ -z "$ip" ] && command -v ifconfig &> /dev/null; then
        ip=$(ifconfig en0 2>/dev/null | grep 'inet ' | awk '{print $2}')
        if [ -z "$ip" ]; then
            ip=$(ifconfig en1 2>/dev/null | grep 'inet ' | awk '{print $2}')
        fi
    fi

    # Method 4: Windows (Git Bash/WSL) - try ipconfig
    if [ -z "$ip" ] && command -v ipconfig.exe &> /dev/null; then
        ip=$(ipconfig.exe 2>/dev/null | grep -A 10 "Ethernet\|Wi-Fi" | grep "IPv4" | head -1 | awk -F': ' '{print $2}' | tr -d '\r')
    fi

    # Filter out localhost and docker IPs
    if [[ "$ip" == "127."* ]] || [[ "$ip" == "172."* ]] || [[ -z "$ip" ]]; then
        ip=""
    fi

    echo "$ip"
}

# Update base_url in config.yaml
update_base_url() {
    local config_file="$1"
    local new_url="$2"

    if [ -f "$config_file" ]; then
        # Use sed to replace base_url line
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS sed requires empty string for -i
            sed -i '' "s|base_url:.*|base_url: \"$new_url\"|" "$config_file"
        else
            sed -i "s|base_url:.*|base_url: \"$new_url\"|" "$config_file"
        fi
    fi
}

cmd_init() {
    print_header
    echo ""
    echo "Initializing RFBooking configuration..."
    echo ""

    # Create directories
    mkdir -p "$CONFIG_DIR" "$DATA_DIR"

    # Check if config already exists
    if [ -f "$CONFIG_DIR/config.yaml" ]; then
        print_warning "Config file already exists at $CONFIG_DIR/config.yaml"
        read -p "Overwrite? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            echo "Keeping existing config."
            return
        fi
    fi

    # Try to copy from running container first, otherwise use local
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Copying config from running container..."
        docker cp "${CONTAINER_NAME}:/app/config/config.example.yaml" "$CONFIG_DIR/config.yaml"
    elif [ -f "config/config.example.yaml" ]; then
        cp "config/config.example.yaml" "$CONFIG_DIR/config.yaml"
    else
        print_error "Could not find config template."
        echo "Please start the container first or run from the project directory."
        exit 1
    fi

    # Detect LAN IP and update config
    echo ""
    echo "Detecting network configuration..."
    LAN_IP=$(detect_lan_ip)

    if [ -n "$LAN_IP" ]; then
        BASE_URL="http://${LAN_IP}:${DEFAULT_PORT}"
        update_base_url "$CONFIG_DIR/config.yaml" "$BASE_URL"
        print_success "Detected LAN IP: $LAN_IP"
        print_success "Set base_url to: $BASE_URL"
    else
        print_warning "Could not auto-detect LAN IP"
        echo "  Please manually set 'app.base_url' in config.yaml"
    fi

    echo ""
    print_success "Config file created at $CONFIG_DIR/config.yaml"
    echo ""
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${YELLOW}  IMPORTANT: Edit config.yaml before use!${NC}"
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════${NC}"
    echo ""
    echo "You MUST change these settings:"
    echo ""
    echo -e "  ${CYAN}organization.name${NC}    Your company name"
    echo -e "  ${CYAN}admin.email${NC}          Your administrator email"
    echo -e "  ${CYAN}email.enabled${NC}        Set to 'true'"
    echo -e "  ${CYAN}email.smtp_*${NC}         Your SMTP server settings"
    echo ""
    echo "Edit the file:"
    echo -e "  ${BOLD}nano $CONFIG_DIR/config.yaml${NC}"
    echo ""
    echo "Then reload configuration:"
    echo -e "  ${BOLD}$0 reload${NC}"
    echo ""

    if [ -n "$LAN_IP" ]; then
        echo -e "${GREEN}════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  Other users can access the system at:${NC}"
        echo -e "${GREEN}  ${BOLD}http://${LAN_IP}:${DEFAULT_PORT}${NC}"
        echo -e "${GREEN}════════════════════════════════════════════${NC}"
    fi
}

cmd_info() {
    print_header
    echo ""

    # Detect LAN IP
    LAN_IP=$(detect_lan_ip)

    echo "Access URLs:"
    echo -e "  Local:   ${CYAN}http://localhost:${DEFAULT_PORT}${NC}"

    if [ -n "$LAN_IP" ]; then
        echo -e "  Network: ${CYAN}http://${LAN_IP}:${DEFAULT_PORT}${NC}"
        echo ""
        echo -e "${GREEN}════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  Share this URL with other users:${NC}"
        echo -e "${GREEN}  ${BOLD}http://${LAN_IP}:${DEFAULT_PORT}${NC}"
        echo -e "${GREEN}════════════════════════════════════════════${NC}"
    else
        print_warning "Could not detect LAN IP address"
        echo ""
        echo "To find your IP manually:"
        echo "  Windows: ipconfig"
        echo "  Mac:     ifconfig en0 | grep inet"
        echo "  Linux:   hostname -I"
    fi

    # Show config base_url if different
    if [ -f "$CONFIG_DIR/config.yaml" ]; then
        CONFIGURED_URL=$(grep "base_url:" "$CONFIG_DIR/config.yaml" | awk '{print $2}' | tr -d '"')
        if [ -n "$CONFIGURED_URL" ] && [ "$CONFIGURED_URL" != "http://${LAN_IP}:${DEFAULT_PORT}" ]; then
            echo ""
            echo -e "Configured base_url: ${YELLOW}${CONFIGURED_URL}${NC}"
            if [ -n "$LAN_IP" ]; then
                echo -e "${YELLOW}  Note: This differs from detected IP. Run '$0 init' to update.${NC}"
            fi
        fi
    fi
}

cmd_reload() {
    print_header
    check_docker
    check_container_running

    echo ""
    echo "Reloading configuration..."

    # Restart FastAPI to reload config
    docker exec "$CONTAINER_NAME" supervisorctl restart fastapi

    sleep 3

    # Check if FastAPI is healthy
    if docker exec "$CONTAINER_NAME" curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Configuration reloaded successfully!"
        echo ""
        cmd_info
    else
        print_error "FastAPI failed to restart. Check logs with: $0 logs"
        exit 1
    fi
}

cmd_restart() {
    print_header
    check_docker
    check_container_running

    echo ""
    echo "Restarting container..."
    docker restart "$CONTAINER_NAME"

    echo "Waiting for services to start..."
    sleep 10

    if docker ps --filter "name=$CONTAINER_NAME" --filter "health=healthy" | grep -q "$CONTAINER_NAME"; then
        print_success "Container restarted successfully!"
    else
        print_warning "Container restarted but may still be initializing."
        echo "Check status with: $0 status"
    fi
}

cmd_status() {
    print_header
    check_docker

    echo ""
    echo "Container Status:"
    echo "-----------------"

    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME")
        HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "N/A")

        echo "  Container: ${CONTAINER_NAME}"
        echo "  Status:    ${CONTAINER_STATUS}"
        echo "  Health:    ${HEALTH_STATUS}"
        echo ""
        echo "Service Status:"
        echo "---------------"
        docker exec "$CONTAINER_NAME" supervisorctl status
        echo ""

        if [ "$HEALTH_STATUS" = "healthy" ]; then
            print_success "RFBooking is running"
            echo ""
            cmd_info
        else
            print_warning "Services may still be initializing"
        fi
    else
        print_error "Container '${CONTAINER_NAME}' is not running"
    fi
}

cmd_logs() {
    check_docker
    check_container_running

    echo "Following container logs (Ctrl+C to exit)..."
    docker logs -f "$CONTAINER_NAME"
}

cmd_shell() {
    check_docker
    check_container_running

    echo "Opening shell in container..."
    docker exec -it "$CONTAINER_NAME" /bin/bash
}

cmd_backup() {
    print_header
    check_docker
    check_container_running

    BACKUP_FILE="rfbooking-backup-$(date +%Y%m%d-%H%M%S).db"

    echo ""
    echo "Creating database backup..."

    docker cp "${CONTAINER_NAME}:/data/rfbooking.db" "./$BACKUP_FILE"

    print_success "Database backed up to $BACKUP_FILE"
}

cmd_help() {
    print_header
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  init      Initialize configuration (first-time setup)"
    echo "  info      Show access URLs and network information"
    echo "  reload    Reload configuration (restart FastAPI)"
    echo "  restart   Restart the entire container"
    echo "  status    Show container and service status"
    echo "  logs      Follow container logs"
    echo "  shell     Open bash shell in container"
    echo "  backup    Backup SQLite database"
    echo "  help      Show this help message"
    echo ""
    echo "First-time setup:"
    echo "  1. docker-compose up -d    # Start container"
    echo "  2. $0 init                 # Get config file (auto-detects IP)"
    echo "  3. Edit config/config.yaml # Set organization, admin, email"
    echo "  4. $0 reload               # Apply changes"
    echo ""
}

# Main
case "${1:-help}" in
    init)
        cmd_init
        ;;
    info)
        cmd_info
        ;;
    reload)
        cmd_reload
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    shell)
        cmd_shell
        ;;
    backup)
        cmd_backup
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        print_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
