"""Sistema de Videovigilancia Resiliente - Script principal."""

import logging
import signal
import sys
import time

import numpy as np

from src.config import Settings
from src.capture import RTSPCapture
from src.detection import MotionDetector, YOLODetector, VisDroneDetector
from src.alerts import TelegramAlert, TelegramCommands
from src.tracking import VehicleCounter

logger = logging.getLogger(__name__)

# Flag global para shutdown graceful
_running = True


def shutdown_handler(signum, frame):
    """Maneja SIGTERM y SIGINT para apagado graceful."""
    global _running
    sig_name = signal.Signals(signum).name
    logger.info("Señal %s recibida, apagando...", sig_name)
    _running = False


def crop_roi(frame: np.ndarray, roi: tuple) -> np.ndarray:
    """Recorta la región de interés del frame.

    Args:
        frame: Imagen BGR completa.
        roi: Tupla (x1, y1, x2, y2) como porcentaje (0.0-1.0).

    Returns:
        Frame recortado a la ROI.
    """
    h, w = frame.shape[:2]
    x1 = int(roi[0] * w)
    y1 = int(roi[1] * h)
    x2 = int(roi[2] * w)
    y2 = int(roi[3] * h)
    return frame[y1:y2, x1:x2]


def adjust_detections_to_full_frame(detections: list, roi: tuple, frame_shape: tuple) -> list:
    """Ajusta las coordenadas de bounding boxes del crop al frame completo.

    Args:
        detections: Lista de Detection con bbox relativas al crop.
        roi: Tupla (x1, y1, x2, y2) como porcentaje (0.0-1.0).
        frame_shape: Shape del frame completo (h, w, c).

    Returns:
        Lista de Detection con bbox ajustadas al frame completo.
    """
    h, w = frame_shape[:2]
    offset_x = int(roi[0] * w)
    offset_y = int(roi[1] * h)

    for det in detections:
        bx1, by1, bx2, by2 = det.bbox
        det.bbox = (bx1 + offset_x, by1 + offset_y, bx2 + offset_x, by2 + offset_y)

    return detections


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
    yolo_detector = None
    if settings.YOLO_MODEL == "visdrone":
        logger.info("Usando modelo VisDrone (vigilancia aérea/elevada).")
        yolo_detector = VisDroneDetector(
            confidence_threshold=settings.YOLO_CONFIDENCE,
        )
    else:
        logger.info("Usando modelo COCO (YOLOv8n genérico).")
        yolo_detector = YOLODetector(
            confidence_threshold=settings.YOLO_CONFIDENCE,
            target_classes=settings.YOLO_TARGET_CLASSES,
        )
    telegram = TelegramAlert(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID,
        cooldown=settings.ALERT_COOLDOWN,
    )
    vehicle_counter = VehicleCounter(cooldown=10.0)

    # ROI para crop
    roi = settings.DETECTION_ROI
    if roi:
        logger.info("ROI configurada: x1=%.2f y1=%.2f x2=%.2f y2=%.2f", *roi)
    else:
        logger.info("Sin ROI configurada, usando frame completo.")

    # Registrar señales de apagado
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Iniciar listener de comandos del bot
    commands = TelegramCommands(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID,
        capture=capture,
        yolo_detector=yolo_detector,
        motion_detector=motion_detector,
        vehicle_counter=vehicle_counter,
    )
    commands.start()

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

            # Detección de movimiento (sobre frame completo)
            motion = motion_detector.detect(frame)

            if motion:
                logger.info("Movimiento detectado, ejecutando YOLO...")

                # Capturar frame fresco para YOLO
                fresh_frame = capture.read_frame()
                if fresh_frame is None:
                    fresh_frame = frame

                # Aplicar crop ROI si está configurado
                if roi:
                    yolo_input = crop_roi(fresh_frame, roi)
                else:
                    yolo_input = fresh_frame

                detections = yolo_detector.detect(yolo_input)

                # Ajustar coordenadas al frame completo
                if detections and roi:
                    detections = adjust_detections_to_full_frame(
                        detections, roi, fresh_frame.shape
                    )

                if detections:
                    classes = [d.class_name for d in detections]
                    logger.info("YOLO detectó: %s", ", ".join(classes))

                    # Contar vehículos
                    new_vehicles = vehicle_counter.count(detections)
                    if new_vehicles:
                        logger.info("Vehículos nuevos contados: %s", new_vehicles)

                    if not commands.alertas_pausadas:
                        telegram.send_alert(fresh_frame, detections)
                    else:
                        logger.info("Alerta suprimida (pausadas).")

                # Después de YOLO, actualizar referencia de movimiento
                post_frame = capture.read_frame()
                if post_frame is not None:
                    motion_detector.detect(post_frame)

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
