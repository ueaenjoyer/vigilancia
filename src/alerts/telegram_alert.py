"""Módulo de alertas vía Telegram usando la API HTTP directamente."""

import logging
import time
from collections import Counter

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

# Colores BGR para bounding boxes
COLORS = {
    "persona": (0, 255, 0),   # Verde
    "perro": (255, 0, 0),     # Azul
}
DEFAULT_COLOR = (0, 255, 255)  # Amarillo para otras clases


class TelegramAlert:
    """Envía alertas con imagen anotada a Telegram vía HTTP API.

    Args:
        bot_token: Token del bot de Telegram.
        chat_id: ID del chat destino.
        cooldown: Segundos mínimos entre alertas (default 30).
    """

    def __init__(self, bot_token: str, chat_id: str, cooldown: float = 30.0):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.cooldown = cooldown
        self._last_alert_time: float = 0.0
        self._base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _is_in_cooldown(self) -> bool:
        """Verifica si estamos dentro del período de cooldown."""
        elapsed = time.time() - self._last_alert_time
        return elapsed < self.cooldown

    def _draw_detections(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """Dibuja bounding boxes y labels sobre una copia del frame.

        Args:
            frame: Imagen original (numpy array BGR).
            detections: Lista de objetos Detection con atributos:
                        class_name, confidence, bbox (x1, y1, x2, y2).

        Returns:
            Copia del frame con las anotaciones dibujadas.
        """
        annotated = frame.copy()

        for det in detections:
            clase = det.class_name
            confidence = det.confidence
            bbox = det.bbox

            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            color = COLORS.get(clase, DEFAULT_COLOR)

            # Rectángulo
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Label con clase y confianza
            label = f"{clase} {confidence:.0%}"
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )

            # Fondo del label
            cv2.rectangle(
                annotated,
                (x1, y1 - text_h - baseline - 4),
                (x1 + text_w, y1),
                color,
                -1,
            )
            # Texto
            cv2.putText(
                annotated,
                label,
                (x1, y1 - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (0, 0, 0),
                thickness,
            )

        return annotated

    def _build_caption(self, detections: list) -> str:
        """Genera un caption descriptivo para la alerta.

        Args:
            detections: Lista de objetos Detection.

        Returns:
            Texto del caption (ej: '🚨 Detectado: 1 persona, 1 perro').
        """
        counter = Counter(det.class_name for det in detections)
        items = ", ".join(f"{count} {clase}" for clase, count in counter.items())
        return f"🚨 Detectado: {items}"

    def send_alert(self, frame: np.ndarray, detections: list) -> bool:
        """Envía una alerta con imagen anotada a Telegram.

        Args:
            frame: Imagen BGR (numpy array).
            detections: Lista de objetos Detection.

        Returns:
            True si se envió correctamente, False si está en cooldown o hubo error.
        """
        if self._is_in_cooldown():
            logger.debug("Alerta no enviada: en período de cooldown.")
            return False

        try:
            # Dibujar detecciones
            annotated = self._draw_detections(frame, detections)

            # Codificar a JPEG en memoria
            success, buffer = cv2.imencode(".jpg", annotated)
            if not success:
                logger.error("Error al codificar imagen a JPEG.")
                return False

            # Preparar caption
            caption = self._build_caption(detections)

            # Enviar foto vía Telegram API
            url = f"{self._base_url}/sendPhoto"
            files = {"photo": ("alerta.jpg", buffer.tobytes(), "image/jpeg")}
            data = {"chat_id": self.chat_id, "caption": caption}

            response = requests.post(url, data=data, files=files, timeout=10)

            if response.status_code == 200:
                self._last_alert_time = time.time()
                logger.info("Alerta enviada a Telegram: %s", caption)
                return True
            else:
                logger.error(
                    "Telegram respondió con código %d: %s",
                    response.status_code,
                    response.text,
                )
                return False

        except requests.RequestException as e:
            logger.error("Error de red al enviar alerta a Telegram: %s", e)
            return False
        except Exception as e:
            logger.error("Error inesperado al enviar alerta: %s", e)
            return False

    def send_text(self, message: str) -> bool:
        """Envía un mensaje de texto simple a Telegram.

        Útil para notificaciones de inicio del sistema, errores críticos, etc.

        Args:
            message: Texto del mensaje a enviar.

        Returns:
            True si se envió correctamente, False si hubo error.
        """
        try:
            url = f"{self._base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message}

            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                logger.info("Mensaje de texto enviado a Telegram.")
                return True
            else:
                logger.error(
                    "Telegram respondió con código %d: %s",
                    response.status_code,
                    response.text,
                )
                return False

        except requests.RequestException as e:
            logger.error("Error de red al enviar mensaje a Telegram: %s", e)
            return False
        except Exception as e:
            logger.error("Error inesperado al enviar mensaje: %s", e)
            return False
