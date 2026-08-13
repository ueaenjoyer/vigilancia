"""Modelos de datos para el módulo de detección."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True, frozen=True)
class Detection:
    """Resultado de una detección de objeto.

    Attributes:
        class_id: ID numérico de la clase detectada.
        class_name: Nombre legible de la clase.
        confidence: Confianza de la detección (0.0 - 1.0).
        bbox: Bounding box (x1, y1, x2, y2) en píxeles.
    """

    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
