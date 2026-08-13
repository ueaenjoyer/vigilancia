# Sistema de Videovigilancia con YOLO + Telegram

Sistema de detección de personas y perros en tiempo real usando una cámara IP (Tapo/RTSP) con alertas por Telegram.

Optimizado para hardware de bajo consumo (Celeron N3050, 2GB RAM).

---

## Arquitectura

```
Cámara Tapo (RTSP stream2 - baja resolución)
       |
       | OpenCV VideoCapture
       v
  Miniservidor (Debian)
       |
       +-- Etapa 1: Detección de movimiento (diff frames, ~5ms)
       |       |
       |    NO movimiento → dormir
       |    SÍ movimiento ↓
       |
       +-- Etapa 2: YOLOv8n (persona/perro, ~3-5s en CPU)
       |       |
       |    Detección ↓
       |
       +-- Alerta Telegram (foto + bounding boxes)
       |
       +-- [Futuro] Azure AI Foundry (detección pesada)
```

La detección en dos etapas ahorra CPU: YOLO solo corre cuando hay movimiento real.

---

## Hardware

| Componente | Especificación |
|---|---|
| Servidor | HP Notebook - Intel Celeron N3050, 2GB RAM, SSD 120GB |
| SO | Debian 13 (Trixie) |
| Cámara | TP-Link Tapo (RTSP/ONVIF) |
| Red | WiFi 2.4 GHz (misma red local) |

---

## Requisitos previos

1. **Cámara Tapo configurada con RTSP:**
   - Abre la app Tapo → Cámara → Configuración → Avanzado → Cuenta de cámara
   - Crea usuario/contraseña para RTSP
   - La URL será: `rtsp://usuario:contraseña@IP_CAMARA:554/stream2`

2. **Bot de Telegram:**
   - Habla con [@BotFather](https://t.me/BotFather) → `/newbot` → Copia el token
   - Habla con [@userinfobot](https://t.me/userinfobot) → Copia tu Chat ID
   - Envía un mensaje al bot para que pueda responderte

---

## Instalación en el servidor

### Opción A: Script automático

```bash
ssh john@server-john
curl -sSL https://raw.githubusercontent.com/TU_USUARIO/vigilancia/main/scripts/setup-server.sh | bash
```

### Opción B: Manual

```bash
ssh john@server-john

# Instalar dependencias del sistema
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# Clonar repositorio
git clone https://github.com/TU_USUARIO/vigilancia.git ~/vigilancia
cd ~/vigilancia

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
nano .env  # Editar con tus valores reales
```

---

## Configuración

Edita el archivo `.env` en el servidor:

```bash
# REQUERIDAS
RTSP_URL=rtsp://usuario:contraseña@192.168.1.100:554/stream2
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789

# OPCIONALES (valores por defecto)
MOTION_THRESHOLD=25        # Sensibilidad movimiento (mayor = menos sensible)
MOTION_MIN_AREA=500        # Área mínima en px para contar como movimiento
YOLO_CONFIDENCE=0.5        # Confianza mínima YOLO (0.0-1.0)
YOLO_TARGET_CLASSES=0,16   # 0=persona, 16=perro
CAPTURE_INTERVAL=1.0       # Segundos entre capturas
ALERT_COOLDOWN=30          # Segundos mínimos entre alertas
LOG_LEVEL=INFO
```

---

## Ejecución

### Manual (para pruebas)

```bash
cd ~/vigilancia
source venv/bin/activate
python main.py
```

### Como servicio (producción)

El script `setup-server.sh` crea el servicio automáticamente. Si lo haces manual:

```bash
sudo tee /etc/systemd/system/vigilancia.service << 'EOF'
[Unit]
Description=Sistema de Videovigilancia
After=network-online.target
Wants=network-online.target

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
sudo systemctl enable vigilancia
sudo systemctl start vigilancia
```

---

## Deploy (desde tu PC de desarrollo)

```bash
# Deploy completo (push + pull + restart servicio)
make deploy

# Ver logs en tiempo real
make logs

# Estado del servicio
make status

# Reiniciar
make restart

# Detener
make stop
```

---

## Estructura del proyecto

```
vigilancia/
├── main.py                     # Script principal (loop de vigilancia)
├── requirements.txt            # Dependencias Python pinneadas
├── .env.example                # Template de configuración
├── Makefile                    # Comandos de deploy rápido
├── src/
│   ├── capture/
│   │   └── rtsp_capture.py    # Captura RTSP con reconexión automática
│   ├── detection/
│   │   ├── motion.py          # Detección de movimiento (diff frames)
│   │   ├── yolo_detector.py   # YOLOv8n (personas y perros)
│   │   └── models.py          # Dataclass Detection
│   ├── alerts/
│   │   └── telegram_alert.py  # Alertas Telegram con foto
│   └── config/
│       └── settings.py        # Carga de configuración desde .env
├── scripts/
│   ├── setup-server.sh        # Instalación inicial en el servidor
│   └── deploy.sh              # Deploy automatizado
└── docs/                       # Documentación adicional
```

---

## Rendimiento esperado

| Métrica | Valor estimado |
|---|---|
| Detección de movimiento | ~5ms por frame |
| Inferencia YOLOv8n (CPU) | ~3-5 segundos por frame |
| RAM en uso | ~800MB-1.2GB |
| Latencia total (evento → Telegram) | ~5-10 segundos |

**Nota:** YOLOv8n solo corre cuando hay movimiento, así que la CPU está idle la mayor parte del tiempo.

---

## Roadmap

- [x] Captura RTSP con reconexión
- [x] Detección de movimiento por diff frames
- [x] Detección YOLO (personas y perros)
- [x] Alertas Telegram con foto anotada
- [ ] Exportar modelo a OpenVINO (aceleración Intel GPU)
- [ ] Endpoint Azure AI Foundry para detección pesada
- [ ] Grabación de clips cuando hay evento
- [ ] Dashboard web para visualización
- [ ] Múltiples cámaras

---

## Notas

- La primera ejecución descarga el modelo YOLOv8n (~6MB). Requiere Internet.
- El stream RTSP usa `stream2` (baja resolución) para minimizar uso de red y CPU.
- Si la cámara se desconecta, el sistema reintenta automáticamente con backoff exponencial.
- Las alertas tienen cooldown de 30s para no spamear Telegram.
