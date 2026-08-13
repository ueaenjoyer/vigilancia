#!/bin/bash
# setup-server.sh - Configuración inicial del servidor de vigilancia
# Ejecutar en: Debian 13 (miniservidor), usuario: john
# Uso: bash setup-server.sh

set -euo pipefail

REPO_URL="https://github.com/tu-usuario/vigilancia.git"  # TODO: Cambiar por URL real
INSTALL_DIR="$HOME/vigilancia"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="vigilancia"

echo "========================================="
echo " Setup del servidor de vigilancia"
echo "========================================="
echo ""

# --- Instalar dependencias del sistema ---
echo "[1/6] Instalando dependencias del sistema..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git

# --- Clonar repositorio ---
echo ""
echo "[2/6] Clonando repositorio..."
if [ -d "$INSTALL_DIR" ]; then
    echo "  Directorio $INSTALL_DIR ya existe, haciendo pull..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# --- Crear entorno virtual ---
echo ""
echo "[3/6] Creando entorno virtual..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# --- Instalar dependencias Python ---
echo ""
echo "[4/6] Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

# --- Crear .env si no existe ---
echo ""
echo "[5/6] Configurando archivo .env..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "  Archivo .env creado desde .env.example"
    echo "  ⚠️  IMPORTANTE: Edita .env con tus valores reales"
else
    echo "  Archivo .env ya existe, no se modifica"
fi

# --- Crear servicio systemd ---
echo ""
echo "[6/6] Creando servicio systemd..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Sistema de Videovigilancia Resiliente
After=network.target

[Service]
Type=simple
User=john
WorkingDirectory=/home/john/vigilancia
ExecStart=/home/john/vigilancia/venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

echo ""
echo "========================================="
echo " ✅ Setup completado"
echo "========================================="
echo ""
echo "Próximos pasos:"
echo "  1. Edita el archivo .env con tus credenciales:"
echo "     nano ~/vigilancia/.env"
echo ""
echo "  2. Inicia el servicio:"
echo "     sudo systemctl start vigilancia"
echo ""
echo "  3. Verifica el estado:"
echo "     systemctl status vigilancia"
echo ""
echo "  4. Ver logs en tiempo real:"
echo "     journalctl -u vigilancia -f"
echo ""
