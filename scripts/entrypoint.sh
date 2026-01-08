#!/bin/bash
# RFBooking FastAPI OSS - Self-hosted Equipment Booking System
# Copyright (C) 2025 Oleg Tokmakov
# SPDX-License-Identifier: AGPL-3.0-or-later

set -e

echo "============================================"
echo "  RFBooking FastAPI OSS"
echo "  Self-hosted Equipment Booking System"
echo "============================================"

# Create required directories
mkdir -p /var/log/supervisor
mkdir -p /data
mkdir -p /app/config

# Set permissions for mounted directories
chmod 755 /data 2>/dev/null || true
chmod 755 /app/config 2>/dev/null || true

# Copy example config if no config exists
if [ ! -f /app/config/config.yaml ]; then
    echo "No config file found, creating from template..."
    # Use the copy stored outside the mounted volume
    cp /app/config.example.yaml /app/config/config.yaml
    echo ""
    echo "  Initial setup required!"
    echo "  Visit http://localhost:8000/setup to configure."
    echo ""
fi

# Start supervisord in background
echo "Starting services..."
/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf &
SUPERVISOR_PID=$!

# Wait for Ollama to start
echo "Waiting for Ollama to start..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Ollama failed to start after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "Waiting for Ollama... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "Ollama is running!"

# Pull model if not exists
echo "Checking for Llama 3.1 8B model..."
if ! ollama list | grep -q "llama3.1:8b"; then
    echo "============================================"
    echo "  DOWNLOADING AI MODEL"
    echo "============================================"
    echo "Model: Llama 3.1 8B"
    echo "Size:  ~4.7 GB"
    echo ""
    echo "This is a one-time download. The model will"
    echo "be cached for future container restarts."
    echo ""
    echo "Please wait..."
    echo "============================================"

    # Run ollama pull - it shows progress by default
    if ollama pull llama3.1:8b; then
        echo "============================================"
        echo "  MODEL DOWNLOAD COMPLETE"
        echo "============================================"
    else
        echo "============================================"
        echo "  ERROR: Model download failed!"
        echo "  Please check your internet connection"
        echo "  and try restarting the container."
        echo "============================================"
        exit 1
    fi
else
    echo "Llama 3.1 8B model already available (cached)"
fi

# Wait for FastAPI to start
echo "Waiting for FastAPI to start..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: FastAPI failed to start after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "Waiting for FastAPI... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "============================================"
echo "  RFBooking FastAPI OSS is ready!"
echo "============================================"
echo ""
echo "  Open in browser: http://localhost:8000"
echo ""
echo "  First time? You will be redirected to the"
echo "  setup wizard to configure your installation."
echo ""
echo "============================================"

# Keep container running
wait $SUPERVISOR_PID
