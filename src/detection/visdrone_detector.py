"""Detector YOLOv11s entrenado con VisDrone para vigilancia aérea/elevada.

Modelo especializado para cámaras de vigilancia elevadas (como Tapo).
Detecta vehículos pequeños a distancia mucho mejor que YOLOv8n COCO.

Clases VisDrone: pedestrian, people, bicycle, car, van, truck,
                 tricycle, awning-tricycle, bus, motor
"""

import logging
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(__file__).parent.parent.parent / "models"
_DEFAULT_MODEL_PATH = _DEFAULT_MODEL_DIR / "yolo11s_visdrone.onnx"
_MODEL_URL = "https://huggingface.co/RISEF/yolov11s-visdrone/resolve/main/weights/best.onnx"

# Clases VisDrone (10 clases)
VISDRONE_CLASSES = {
    0: "peatón",
    1: "persona",
    2: "bicicleta",
    3: "carro",
    4: "van",
    5: "camión",
    6: "triciclo",
    7: "triciclo-toldo",
    8: "bus",
    9: "moto",
}

# Mapeo de IDs VisDrone a IDs genéricos para el VehicleCounter
# El VehicleCounter usa COCO IDs (2=car, 3=motorcycle, 5=bus, 7=truck)
VISDRONE_TO_COCO = {
    3: 2,   # car → car
    4: 2,   # van → car (contamos vans como carros)
    5: 7,   # truck → truck
    8: 5,   # bus → bus
    9: 3,   # motor → motorcycle
}


class VisDroneDetector:
    """Detector YOLOv11s especializado para VisDrone (vigilancia aérea).

    Optimizado para detectar vehículos pequeños vistos desde cámaras
    elevadas. Output shape: (1, 14, N) = 4 bbox + 10 class scores.

    Args:
        model_path: Ruta al modelo .onnx.
        confidence_threshold: Confianza mínima. Default: 0.3.
        iou_threshold: Umbral IoU para NMS. Default: 0.45.
        target_classes: Lista de IDs VisDrone a detectar.
            Default: [0,1,3,4,5,8,9] (personas + vehículos).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.3,
        iou_threshold: float = 0.45,
        target_classes: Optional[List[int]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        # Default: personas + todos los vehículos
        self.target_classes = target_classes if target_classes is not None else [0, 1, 3, 4, 5, 8, 9]
        self._input_size = 640

        if model_path is None:
            self._model_path = _DEFAULT_MODEL_PATH
        else:
            self._model_path = Path(model_path)

        if not self._model_path.exists():
            self._download_model()

        logger.info(
            "Cargando modelo VisDrone ONNX desde '%s' (conf=%.2f)...",
            self._model_path,
            confidence_threshold,
        )

        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 2
        sess_options.inter_op_num_threads = 2
        sess_options.enable_cpu_mem_arena = True
        sess_options.enable_mem_pattern = True

        self._session = ort.InferenceSession(
            str(self._model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )

        self._input_name = self._session.get_inputs()[0].name
        output_shape = self._session.get_outputs()[0].shape
        logger.info("Modelo VisDrone cargado. Output shape: %s", output_shape)

    def _download_model(self) -> None:
        """Descarga el modelo desde HuggingFace."""
        import requests

        logger.info("Descargando modelo VisDrone desde HuggingFace (%s)...", _MODEL_URL)
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
                    if total_size > 0 and downloaded % (5 * 1024 * 1024) < 8192:
                        pct = (downloaded / total_size) * 100
                        logger.info("Descargando: %.0f%%", pct)

            logger.info(
                "Modelo descargado: %s (%.1f MB)",
                self._model_path,
                downloaded / 1024 / 1024,
            )
        except Exception as e:
            if self._model_path.exists():
                self._model_path.unlink()
            raise RuntimeError(
                f"No se pudo descargar el modelo VisDrone. Error: {e}"
            ) from e

    def _preprocess(self, frame: np.ndarray):
        """Preprocesa el frame para inferencia."""
        h_orig, w_orig = frame.shape[:2]

        scale = min(self._input_size / w_orig, self._input_size / h_orig)
        new_w = int(w_orig * scale)
        new_h = int(h_orig * scale)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_x = (self._input_size - new_w) // 2
        pad_y = (self._input_size - new_h) // 2

        padded = np.full((self._input_size, self._input_size, 3), 114, dtype=np.uint8)
        padded[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        blob = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)

        return blob, scale, pad_x, pad_y

    def detect(self, frame: np.ndarray) -> List:
        """Ejecuta inferencia sobre un frame.

        Returns:
            Lista de Detection con class_id mapeado a COCO para
            compatibilidad con VehicleCounter.
        """
        from .models import Detection

        h_orig, w_orig = frame.shape[:2]
        blob, scale, pad_x, pad_y = self._preprocess(frame)

        outputs = self._session.run(None, {self._input_name: blob})

        # Output shape: (1, 14, N) → transpose a (N, 14)
        predictions = outputs[0][0].transpose()

        boxes = []
        scores = []
        class_ids = []
        class_names = []

        for pred in predictions:
            cx, cy, w, h = pred[:4]
            class_scores = pred[4:]  # 10 clases

            for cls_id in self.target_classes:
                if cls_id >= len(class_scores):
                    continue

                score = float(class_scores[cls_id])
                if score < self.confidence_threshold:
                    continue

                x1 = (cx - w / 2 - pad_x) / scale
                y1 = (cy - h / 2 - pad_y) / scale
                x2 = (cx + w / 2 - pad_x) / scale
                y2 = (cy + h / 2 - pad_y) / scale

                x1 = max(0, min(x1, w_orig))
                y1 = max(0, min(y1, h_orig))
                x2 = max(0, min(x2, w_orig))
                y2 = max(0, min(y2, h_orig))

                boxes.append([x1, y1, x2 - x1, y2 - y1])
                scores.append(score)
                class_ids.append(cls_id)
                class_names.append(VISDRONE_CLASSES.get(cls_id, f"clase_{cls_id}"))

        if not boxes:
            return []

        # NMS
        boxes_np = np.array(boxes, dtype=np.float32)
        scores_np = np.array(scores, dtype=np.float32)

        indices = cv2.dnn.NMSBoxes(
            boxes_np.tolist(),
            scores_np.tolist(),
            self.confidence_threshold,
            self.iou_threshold,
        )

        if indices is None or len(indices) == 0:
            return []

        if isinstance(indices, np.ndarray):
            indices = indices.flatten()

        detections: List[Detection] = []
        for i in indices:
            x, y, w, h = boxes[i]
            bbox = (int(x), int(y), int(x + w), int(y + h))
            visdrone_id = class_ids[i]

            # Mapear a COCO ID para compatibilidad con VehicleCounter
            coco_id = VISDRONE_TO_COCO.get(visdrone_id, visdrone_id)

            detection = Detection(
                class_id=coco_id,
                class_name=class_names[i],
                confidence=scores[i],
                bbox=bbox,
            )
            detections.append(detection)

        if detections:
            logger.info("%d detección(es) VisDrone.", len(detections))

        return detections
