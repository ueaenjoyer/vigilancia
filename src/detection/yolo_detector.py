"""Detección de objetos con YOLOv8n.

Segunda etapa de detección: se activa solo cuando MotionDetector
detecta movimiento, para minimizar uso de recursos.
"""

import logging
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Importación diferida de ultralytics para no cargar el modelo
# hasta que realmente se necesite.
_YOLO = None


def _load_yolo_class():
    """Carga la clase YOLO de ultralytics de forma diferida."""
    global _YOLO
    if _YOLO is None:
        from ultralytics import YOLO
        _YOLO = YOLO
    return _YOLO


class YOLODetector:
    """Detector de objetos basado en YOLOv8n.

    Diseñado para ejecutarse en una laptop auxiliar o cuando hay
    recursos disponibles. Filtra detecciones por clases de interés.

    Args:
        model_path: Ruta al modelo YOLO. Default: 'yolov8n.pt'
            (se descarga automáticamente la primera vez).
        confidence_threshold: Confianza mínima para aceptar detecciones. Default: 0.5.
        target_classes: Lista de IDs de clase a detectar. Default: [0, 16]
            (0=persona, 16=perro).
    """

    # Mapa de nombres de clases COCO relevantes
    CLASS_NAMES = {
        0: "persona",
        16: "perro",
    }

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        target_classes: Optional[List[int]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.target_classes = target_classes if target_classes is not None else [0, 16]

        logger.info(
            "Cargando modelo YOLO desde '%s' (conf=%.2f, clases=%s)...",
            model_path,
            confidence_threshold,
            self.target_classes,
        )

        YOLO = _load_yolo_class()
        self._model = YOLO(model_path)

        logger.info("Modelo YOLO cargado correctamente.")

    def detect(self, frame: np.ndarray) -> List:
        """Ejecuta inferencia YOLO sobre un frame.

        Args:
            frame: Imagen BGR (numpy array).

        Returns:
            Lista de Detection con los objetos detectados que coinciden
            con las clases de interés y superan el umbral de confianza.
        """
        from .models import Detection

        # Redimensionar a 640x640 para optimizar inferencia
        resized = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_LINEAR)

        # Ejecutar inferencia con verbose=False para reducir logs
        results = self._model(resized, verbose=False, conf=self.confidence_threshold)

        detections: List[Detection] = []

        if not results or len(results) == 0:
            return detections

        result = results[0]

        # Factores de escala para mapear bbox al tamaño original
        h_orig, w_orig = frame.shape[:2]
        scale_x = w_orig / 640.0
        scale_y = h_orig / 640.0

        for box in result.boxes:
            class_id = int(box.cls[0])

            # Filtrar por clases de interés
            if class_id not in self.target_classes:
                continue

            confidence = float(box.conf[0])

            # Obtener bbox y escalar a coordenadas originales
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox = (
                int(x1 * scale_x),
                int(y1 * scale_y),
                int(x2 * scale_x),
                int(y2 * scale_y),
            )

            class_name = self.CLASS_NAMES.get(class_id, f"clase_{class_id}")

            detection = Detection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bbox=bbox,
            )
            detections.append(detection)

            logger.debug(
                "Detectado: %s (conf=%.2f) en %s",
                class_name,
                confidence,
                bbox,
            )

        if detections:
            logger.info("%d detección(es) encontrada(s).", len(detections))

        return detections
