#!/usr/bin/env bash
set -euo pipefail

# ArmorIQ MCP Registration Script
CONFIG_PATH="backend/armoriq/armoriq.yaml"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: $CONFIG_PATH not found" >&2
    exit 1
fi

echo "Validating ArmorIQ configuration..."
armoriq validate --config "$CONFIG_PATH"

echo "Registering MCP server with ArmorIQ Control Plane..."
armoriq register --config "$CONFIG_PATH"

echo "Checking status..."
armoriq status
