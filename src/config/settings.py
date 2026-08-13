"""Módulo de configuración del sistema de videovigilancia."""

import os

from dotenv import load_dotenv

# Cargar variables desde .env automáticamente
load_dotenv()


class Settings:
    """Configuración del sistema cargada desde variables de entorno."""

    def __init__(self):
        # Variables requeridas (sin default)
        self.RTSP_URL: str = os.environ.get("RTSP_URL", "")
        self.TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

        # Variables con defaults
        self.MOTION_THRESHOLD: int = int(
            os.environ.get("MOTION_THRESHOLD", "25")
        )
        self.MOTION_MIN_AREA: int = int(
            os.environ.get("MOTION_MIN_AREA", "500")
        )
        self.YOLO_CONFIDENCE: float = float(
            os.environ.get("YOLO_CONFIDENCE", "0.5")
        )
        self.YOLO_TARGET_CLASSES: list[int] = [
            int(c.strip())
            for c in os.environ.get("YOLO_TARGET_CLASSES", "0,16").split(",")
        ]
        self.CAPTURE_INTERVAL: float = float(
            os.environ.get("CAPTURE_INTERVAL", "1.0")
        )
        self.ALERT_COOLDOWN: int = int(
            os.environ.get("ALERT_COOLDOWN", "30")
        )
        self.LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    def validate(self) -> None:
        """Verifica que las variables requeridas estén definidas.

        Raises:
            ValueError: Si alguna variable requerida no está configurada.
        """
        missing = []

        if not self.RTSP_URL:
            missing.append("RTSP_URL")
        if not self.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")

        if missing:
            raise ValueError(
                f"Variables de entorno requeridas no configuradas: {', '.join(missing)}"
            )
