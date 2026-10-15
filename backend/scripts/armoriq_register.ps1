$ErrorActionPreference = "Stop"
$CONFIG_PATH = "backend/armoriq/armoriq.yaml"

if (-not (Test-Path $CONFIG_PATH)) {
    Write-Error "$CONFIG_PATH not found"
    exit 1
}

Write-Host "Validating ArmorIQ configuration..."
armoriq validate --config $CONFIG_PATH

Write-Host "Registering MCP server with ArmorIQ Control Plane..."
armoriq register --config $CONFIG_PATH

Write-Host "Checking status..."
armoriq status
