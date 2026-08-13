"""Detección de objetos con YOLOv8n via ONNX Runtime.

Usa el modelo exportado a ONNX para evitar la dependencia de PyTorch
(~600MB). ONNX Runtime es mucho más ligero (~50MB) y optimizado para CPU.

Segunda etapa de detección: se activa solo cuando MotionDetector
detecta movimiento, para minimizar uso de recursos.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Ruta por defecto del modelo ONNX
_DEFAULT_MODEL_DIR = Path(__file__).parent.parent.parent / "models"
_DEFAULT_MODEL_PATH = _DEFAULT_MODEL_DIR / "yolov8n.onnx"
_MODEL_URL = "https://github.com/ueaenjoyer/vigilancia/releases/download/v0.1.0/yolov8n.onnx"

# Clases COCO (80 clases)
COCO_CLASSES = {
    0: "persona",
    1: "bicicleta",
    2: "coche",
    3: "moto",
    5: "autobus",
    7: "camion",
    14: "pajaro",
    15: "gato",
    16: "perro",
    17: "caballo",
}


class YOLODetector:
    """Detector de objetos basado en YOLOv8n con ONNX Runtime.

    Diseñado para hardware de bajo consumo (Celeron N3050, 2GB RAM).
    No requiere PyTorch ni ultralytics.

    Args:
        model_path: Ruta al modelo .onnx. Si no existe, intenta descargarlo.
        confidence_threshold: Confianza mínima para aceptar detecciones. Default: 0.5.
        iou_threshold: Umbral IoU para NMS (Non-Maximum Suppression). Default: 0.45.
        target_classes: Lista de IDs de clase a detectar. Default: [0, 16]
            (0=persona, 16=perro).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        target_classes: Optional[List[int]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.target_classes = target_classes if target_classes is not None else [0, 16]
        self._input_size = 640  # YOLOv8n espera 640x640

        # Resolver ruta del modelo
        if model_path is None:
            self._model_path = _DEFAULT_MODEL_PATH
        else:
            self._model_path = Path(model_path)

        # Descargar modelo si no existe
        if not self._model_path.exists():
            self._download_model()

        # Cargar modelo ONNX
        logger.info(
            "Cargando modelo YOLO ONNX desde '%s' (conf=%.2f, clases=%s)...",
            self._model_path,
            confidence_threshold,
            self.target_classes,
        )

        import onnxruntime as ort

        # Usar solo CPU, con optimizaciones
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 2  # Celeron tiene 2 cores

        self._session = ort.InferenceSession(
            str(self._model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )

        self._input_name = self._session.get_inputs()[0].name
        logger.info("Modelo YOLO ONNX cargado correctamente.")

    def _download_model(self) -> None:
        """Descarga el modelo YOLOv8n.onnx si no existe localmente."""
        import requests

        logger.info("Modelo no encontrado. Descargando desde %s...", _MODEL_URL)

        # Crear directorio models/ si no existe
        self._model_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            response = requests.get(_MODEL_URL, stream=True, timeout=120)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(self._model_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) < 8192:  # Log cada ~1MB
                            logger.info("Descargando modelo: %.0f%%", pct)

            logger.info("Modelo descargado: %s (%.1f MB)", self._model_path, downloaded / 1024 / 1024)

        except Exception as e:
            # Limpiar archivo parcial
            if self._model_path.exists():
                self._model_path.unlink()
            raise RuntimeError(
                f"No se pudo descargar el modelo ONNX. "
                f"Descárgalo manualmente desde {_MODEL_URL} "
                f"y colócalo en {self._model_path}. Error: {e}"
            ) from e

    def _preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, float, float, int, int]:
        """Preprocesa el frame para inferencia YOLOv8.

        Args:
            frame: Imagen BGR (numpy array).

        Returns:
            Tuple de (blob, scale_x, scale_y, pad_x, pad_y) para mapear
            las detecciones de vuelta a coordenadas originales.
        """
        h_orig, w_orig = frame.shape[:2]

        # Letterbox resize manteniendo aspect ratio
        scale = min(self._input_size / w_orig, self._input_size / h_orig)
        new_w = int(w_orig * scale)
        new_h = int(h_orig * scale)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Padding para llegar a 640x640
        pad_x = (self._input_size - new_w) // 2
        pad_y = (self._input_size - new_h) // 2

        padded = np.full(
            (self._input_size, self._input_size, 3), 114, dtype=np.uint8
        )
        padded[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        # BGR -> RGB, HWC -> CHW, normalizar a [0, 1], añadir batch dim
        blob = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)

        return blob, scale, pad_x, pad_y

    def _postprocess(
        self,
        output: np.ndarray,
        scale: float,
        pad_x: int,
        pad_y: int,
        orig_w: int,
        orig_h: int,
    ) -> List:
        """Postprocesa la salida de YOLOv8 aplicando NMS y filtros.

        YOLOv8 output shape: (1, 84, 8400) = (batch, 4_bbox + 80_clases, detecciones)

        Args:
            output: Salida cruda del modelo.
            scale: Factor de escala usado en preprocess.
            pad_x: Padding X aplicado.
            pad_y: Padding Y aplicado.
            orig_w: Ancho original de la imagen.
            orig_h: Alto original de la imagen.

        Returns:
            Lista de Detection.
        """
        from .models import Detection

        # output shape: (1, 84, 8400) -> transpose a (8400, 84)
        predictions = output[0].transpose()

        detections: List[Detection] = []
        boxes = []
        scores = []
        class_ids = []

        for pred in predictions:
            # pred: [cx, cy, w, h, class_scores...]
            cx, cy, w, h = pred[:4]
            class_scores = pred[4:]

            # Filtrar por clases de interés
            for class_id in self.target_classes:
                if class_id >= len(class_scores):
                    continue

                score = float(class_scores[class_id])
                if score < self.confidence_threshold:
                    continue

                # Convertir de centro/ancho a esquinas
                x1 = cx - w / 2
                y1 = cy - h / 2
                x2 = cx + w / 2
                y2 = cy + h / 2

                # Remover padding y escalar a coordenadas originales
                x1 = (x1 - pad_x) / scale
                y1 = (y1 - pad_y) / scale
                x2 = (x2 - pad_x) / scale
                y2 = (y2 - pad_y) / scale

                # Clamp a límites de la imagen
                x1 = max(0, min(x1, orig_w))
                y1 = max(0, min(y1, orig_h))
                x2 = max(0, min(x2, orig_w))
                y2 = max(0, min(y2, orig_h))

                boxes.append([x1, y1, x2 - x1, y2 - y1])  # formato xywh para NMS
                scores.append(score)
                class_ids.append(class_id)

        if not boxes:
            return detections

        # Non-Maximum Suppression
        boxes_np = np.array(boxes, dtype=np.float32)
        scores_np = np.array(scores, dtype=np.float32)

        indices = cv2.dnn.NMSBoxes(
            boxes_np.tolist(),
            scores_np.tolist(),
            self.confidence_threshold,
            self.iou_threshold,
        )

        if indices is None or len(indices) == 0:
            return detections

        # indices puede ser ndarray o list según versión de OpenCV
        if isinstance(indices, np.ndarray):
            indices = indices.flatten()

        for i in indices:
            x, y, w, h = boxes[i]
            bbox = (int(x), int(y), int(x + w), int(y + h))
            class_id = class_ids[i]
            class_name = COCO_CLASSES.get(class_id, f"clase_{class_id}")

            detection = Detection(
                class_id=class_id,
                class_name=class_name,
                confidence=scores[i],
                bbox=bbox,
            )
            detections.append(detection)

            logger.debug(
                "Detectado: %s (conf=%.2f) en %s",
                class_name,
                scores[i],
                bbox,
            )

        if detections:
            logger.info("%d detección(es) encontrada(s).", len(detections))

        return detections

    def detect(self, frame: np.ndarray) -> List:
        """Ejecuta inferencia YOLO sobre un frame.

        Args:
            frame: Imagen BGR (numpy array).

        Returns:
            Lista de Detection con los objetos detectados que coinciden
            con las clases de interés y superan el umbral de confianza.
        """
        h_orig, w_orig = frame.shape[:2]

        # Preprocesar
        blob, scale, pad_x, pad_y = self._preprocess(frame)

        # Inferencia
        outputs = self._session.run(None, {self._input_name: blob})

        # Postprocesar
        return self._postprocess(
            outputs[0], scale, pad_x, pad_y, w_orig, h_orig
        )
