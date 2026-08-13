"""Detección de movimiento por diferencia contra fondo de referencia.

Compara cada frame contra un fondo de referencia que se actualiza
lentamente. Esto permite detectar objetos nuevos (carros, personas)
incluso si se mueven despacio, porque contrastan contra el fondo estático.
"""

import logging
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MotionDetector:
    """Detecta movimiento comparando contra un fondo de referencia.

    Usa un modelo de fondo que se actualiza lentamente (learning rate bajo).
    Cualquier objeto nuevo que aparezca contrasta contra el fondo y se detecta.

    Args:
        threshold: Umbral de binarización (0-255). Default: 20.
        min_area: Área mínima en píxeles para considerar movimiento. Default: 300.
        learning_rate: Velocidad de actualización del fondo (0.0-1.0).
            Más bajo = fondo cambia más lento = detecta objetos que se quedan.
            Default: 0.005.
    """

    def __init__(
        self,
        threshold: int = 25,
        min_area: int = 500,
        learning_rate: float = 0.005,
    ) -> None:
        self.threshold = threshold
        self.min_area = min_area
        self._learning_rate = learning_rate
        self._bg_gray: Optional[np.ndarray] = None
        self._frame_count = 0
        self._warmup_frames = 5  # Frames para establecer el fondo inicial
        logger.info(
            "MotionDetector inicializado (threshold=%d, min_area=%d, lr=%.4f)",
            threshold,
            min_area,
            learning_rate,
        )

    def detect(self, frame: np.ndarray) -> bool:
        """Analiza un frame y determina si hay movimiento.

        Compara contra el fondo de referencia en vez del frame anterior.
        Esto permite detectar objetos nuevos aunque estén quietos.

        Args:
            frame: Imagen BGR (numpy array) del frame actual.

        Returns:
            True si se detecta movimiento, False en caso contrario.
        """
        # Convertir a escala de grises y suavizar (kernel pequeño)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)

        self._frame_count += 1

        # Primeros frames: construir el fondo de referencia
        if self._bg_gray is None:
            self._bg_gray = gray.astype(np.float32)
            logger.debug("Fondo de referencia inicializado.")
            return False

        if self._frame_count <= self._warmup_frames:
            # Acumular promedio para el fondo inicial
            cv2.accumulateWeighted(gray, self._bg_gray, 0.5)
            return False

        # Convertir fondo a uint8 para comparar
        bg_uint8 = self._bg_gray.astype(np.uint8)

        # Diferencia absoluta contra el fondo
        delta = cv2.absdiff(gray, bg_uint8)

        # Umbralización binaria
        _, thresh = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)

        # Dilatar para conectar regiones cercanas
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Encontrar contornos
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Verificar si algún contorno supera el área mínima
        motion_detected = False
        max_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.min_area:
                motion_detected = True
                if area > max_area:
                    max_area = area

        if motion_detected:
            logger.debug("Movimiento detectado (area_max=%.0f).", max_area)
            # Cuando hay movimiento, NO actualizar el fondo rápido
            # (no queremos que el objeto se "integre" al fondo)
            cv2.accumulateWeighted(gray, self._bg_gray, self._learning_rate * 0.1)
        else:
            # Sin movimiento: actualizar fondo normalmente
            cv2.accumulateWeighted(gray, self._bg_gray, self._learning_rate)

        return motion_detected

    def reset(self) -> None:
        """Reinicia el detector descartando el fondo de referencia."""
        self._bg_gray = None
        self._frame_count = 0
        logger.debug("MotionDetector reiniciado.")
