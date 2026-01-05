#!/bin/bash
# RFBooking FastAPI OSS - Self-hosted Equipment Booking System
# Copyright (C) 2025 Oleg Tokmakov
# SPDX-License-Identifier: AGPL-3.0-or-later

set -e

echo "============================================"
echo "  RFBooking FastAPI OSS"
echo "  Self-hosted Equipment Booking System"
echo "============================================"

# Create log directory
mkdir -p /var/log/supervisor

# Copy example config if no config exists
if [ ! -f /app/config/config.yaml ]; then
    echo "No config file found, copying example config..."
    cp /app/config/config.example.yaml /app/config/config.yaml
    echo "Please update /app/config/config.yaml with your settings"
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
    echo "Downloading Llama 3.1 8B model (this may take a while on first run)..."
    ollama pull llama3.1:8b
    echo "Model downloaded successfully!"
else
    echo "Llama 3.1 8B model already available"
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
echo "  Access the application at:"
echo "  http://localhost:8000"
echo "============================================"

# Keep container running
wait $SUPERVISOR_PID
