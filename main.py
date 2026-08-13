"""Sistema de Videovigilancia Resiliente - Script principal."""

import logging
import signal
import sys
import time

from src.config import Settings
from src.capture import RTSPCapture
from src.detection import MotionDetector, YOLODetector
from src.alerts import TelegramAlert

logger = logging.getLogger(__name__)

# Flag global para shutdown graceful
_running = True


def shutdown_handler(signum, frame):
    """Maneja SIGTERM y SIGINT para apagado graceful."""
    global _running
    sig_name = signal.Signals(signum).name
    logger.info("Señal %s recibida, apagando...", sig_name)
    _running = False


def main():
    global _running

    # Cargar configuración
    settings = Settings()
    settings.validate()

    # Configurar logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Iniciando sistema de vigilancia...")

    # Inicializar componentes
    capture = RTSPCapture(settings.RTSP_URL)
    motion_detector = MotionDetector(
        threshold=settings.MOTION_THRESHOLD,
        min_area=settings.MOTION_MIN_AREA,
    )
    yolo_detector = YOLODetector(
        confidence_threshold=settings.YOLO_CONFIDENCE,
        target_classes=settings.YOLO_TARGET_CLASSES,
    )
    telegram = TelegramAlert(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID,
        cooldown=settings.ALERT_COOLDOWN,
    )

    # Registrar señales de apagado
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Mensaje de inicio
    telegram.send_text("✅ Sistema de vigilancia iniciado")
    logger.info("Sistema listo. Intervalo de captura: %.1fs", settings.CAPTURE_INTERVAL)

    # Loop principal
    while _running:
        try:
            frame = capture.read_frame()

            if frame is None:
                logger.debug("No se obtuvo frame, reintentando...")
                time.sleep(1)
                continue

            # Detección de movimiento
            motion = motion_detector.detect(frame)

            if motion:
                logger.info("Movimiento detectado, ejecutando YOLO...")
                detections = yolo_detector.detect(frame)

                if detections:
                    classes = [d.class_name for d in detections]
                    logger.info("YOLO detectó: %s", ", ".join(classes))
                    telegram.send_alert(frame, detections)

            time.sleep(settings.CAPTURE_INTERVAL)

        except Exception as e:
            logger.exception("Error en loop principal: %s", e)
            time.sleep(5)

    # Cleanup
    logger.info("Apagando sistema...")
    capture.release()
    telegram.send_text("⛔ Sistema de vigilancia apagado")
    logger.info("Sistema apagado correctamente.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical("Error crítico: %s", e, exc_info=True)
        # Intentar notificar por Telegram antes de morir
        try:
            settings = Settings()
            telegram = TelegramAlert(
                bot_token=settings.TELEGRAM_BOT_TOKEN,
                chat_id=settings.TELEGRAM_CHAT_ID,
            )
            telegram.send_text(f"💀 Sistema caído por error crítico: {e}")
        except Exception:
            pass
        sys.exit(1)
