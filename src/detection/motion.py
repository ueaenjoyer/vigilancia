"""Detección de movimiento por diferencia de frames.

Algoritmo ligero optimizado para Raspberry Pi Zero 2 W.
No requiere IA ni conexión a Internet.
"""

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MotionDetector:
    """Detecta movimiento comparando frames consecutivos.

    Usa diferencia absoluta entre frames en escala de grises,
    con suavizado gaussiano y umbralización para reducir ruido.

    Args:
        threshold: Umbral de binarización (0-255). Default: 25.
        min_area: Área mínima en píxeles para considerar movimiento. Default: 500.
    """

    def __init__(self, threshold: int = 25, min_area: int = 500) -> None:
        self.threshold = threshold
        self.min_area = min_area
        self._prev_gray: Optional[np.ndarray] = None
        logger.info(
            "MotionDetector inicializado (threshold=%d, min_area=%d)",
            threshold,
            min_area,
        )

    def detect(self, frame: np.ndarray) -> bool:
        """Analiza un frame y determina si hay movimiento.

        Args:
            frame: Imagen BGR (numpy array) del frame actual.

        Returns:
            True si se detecta movimiento, False en caso contrario.
            El primer frame siempre retorna False (no hay referencia).
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Aplicar suavizado para reducir ruido
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # Primer frame: guardar referencia y retornar False
        if self._prev_gray is None:
            self._prev_gray = gray
            logger.debug("Primer frame almacenado como referencia.")
            return False

        # Diferencia absoluta entre frame actual y anterior
        delta = cv2.absdiff(self._prev_gray, gray)

        # Umbralización binaria
        _, thresh = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)

        # Dilatar para rellenar huecos
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Encontrar contornos
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Actualizar frame anterior
        self._prev_gray = gray

        # Verificar si algún contorno supera el área mínima
        for contour in contours:
            if cv2.contourArea(contour) >= self.min_area:
                logger.debug("Movimiento detectado (area=%.0f).", cv2.contourArea(contour))
                return True

        return False

    def reset(self) -> None:
        """Reinicia el detector descartando el frame de referencia."""
        self._prev_gray = None
        logger.debug("MotionDetector reiniciado.")
