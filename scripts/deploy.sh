#!/bin/bash
# deploy.sh - Deploy desde máquina de desarrollo al servidor
# Uso: bash scripts/deploy.sh

set -euo pipefail

SERVER="john@server-john"
REMOTE_DIR="~/vigilancia"

echo "========================================="
echo " Deploy al servidor de vigilancia"
echo "========================================="
echo ""

# --- Push local ---
echo "[1/3] Haciendo git push..."
git push
echo "  ✅ Push completado"

# --- Deploy remoto ---
echo ""
echo "[2/3] Desplegando en servidor..."
ssh "$SERVER" "cd $REMOTE_DIR && git pull && source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart vigilancia"
echo "  ✅ Deploy completado"

# --- Verificar estado ---
echo ""
echo "[3/3] Estado del servicio:"
ssh "$SERVER" "systemctl status vigilancia"

echo ""
echo "========================================="
echo " ✅ Deploy exitoso"
echo "========================================="
