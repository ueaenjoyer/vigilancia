"""Módulo de detección en dos etapas.

Etapa 1 - MotionDetector: Detección ligera de movimiento por diferencia
    de frames. Se ejecuta en la Raspberry Pi con mínimo consumo de CPU/RAM.

Etapa 2 - YOLODetector: Clasificación de objetos con YOLOv8n. Se activa
    solo cuando la etapa 1 detecta movimiento, para ahorrar recursos.

Uso típico:
    from detection import MotionDetector, YOLODetector

    motion = MotionDetector(threshold=25, min_area=500)
    yolo = YOLODetector(confidence_threshold=0.5)

    if motion.detect(frame):
        detections = yolo.detect(frame)
"""

from .motion import MotionDetector
from .yolo_detector import YOLODetector
from .visdrone_detector import VisDroneDetector

__all__ = ["MotionDetector", "YOLODetector", "VisDroneDetector"]
