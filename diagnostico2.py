"""Diagnóstico largo (2 minutos) con VisDrone + crop ROI.

Ejecutar:
    python diagnostico2.py

Guarda imágenes en /tmp/vigilancia_debug/ cuando detecta movimiento.
Usa el modelo VisDrone si YOLO_MODEL=visdrone en .env.
"""

import os
import time

import cv2
import numpy as np

from src.config import Settings
from src.capture import RTSPCapture
from src.detection import MotionDetector, YOLODetector, VisDroneDetector
from src.tracking import VehicleCounter

OUTPUT_DIR = "/tmp/vigilancia_debug"
DURATION = 120  # 2 minutos


def crop_roi(frame, roi):
    """Recorta ROI del frame."""
    h, w = frame.shape[:2]
    x1 = int(roi[0] * w)
    y1 = int(roi[1] * h)
    x2 = int(roi[2] * w)
    y2 = int(roi[3] * h)
    return frame[y1:y2, x1:x2]


def main():
    settings = Settings()
    settings.validate()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print(f"DIAGNÓSTICO LARGO ({DURATION}s) - VisDrone + Crop")
    print(f"Imágenes se guardan en: {OUTPUT_DIR}")
    print("=" * 60)
    print(f"RTSP: {'stream2' if 'stream2' in settings.RTSP_URL else 'stream1'}")
    print(f"YOLO_MODEL: {settings.YOLO_MODEL}")
    print(f"YOLO_CONFIDENCE: {settings.YOLO_CONFIDENCE}")
    print(f"DETECTION_ROI: {settings.DETECTION_ROI}")
    print()

    capture = RTSPCapture(settings.RTSP_URL)

    # Seleccionar detector
    if settings.YOLO_MODEL == "visdrone":
        print("Usando modelo VisDrone (especializado en vigilancia aérea)")
        detector = VisDroneDetector(confidence_threshold=settings.YOLO_CONFIDENCE)
    else:
        print("Usando modelo COCO (YOLOv8n genérico)")
        detector = YOLODetector(
            confidence_threshold=settings.YOLO_CONFIDENCE,
            target_classes=settings.YOLO_TARGET_CLASSES,
        )

    motion_detector = MotionDetector(
        threshold=settings.MOTION_THRESHOLD,
        min_area=settings.MOTION_MIN_AREA,
    )
    vehicle_counter = VehicleCounter(cooldown=10.0)
    roi = settings.DETECTION_ROI

    time.sleep(2)

    # Guardar frames de referencia
    print("\nGuardando frames de referencia...")
    frame = capture.read_frame()
    if frame is not None:
        path = os.path.join(OUTPUT_DIR, "referencia_full.jpg")
        cv2.imwrite(path, frame)
        print(f"  → {path} (frame completo)")

        if roi:
            cropped = crop_roi(frame, roi)
            path2 = os.path.join(OUTPUT_DIR, "referencia_crop.jpg")
            cv2.imwrite(path2, cropped)
            print(f"  → {path2} (crop ROI: {cropped.shape[1]}x{cropped.shape[0]})")

    print(f"\nMonitoreando por {DURATION} segundos...")
    print("-" * 60)

    start = time.perf_counter()
    frame_num = 0
    motion_count = 0
    yolo_runs = 0
    yolo_detections = 0
    vehicles_counted = 0

    while (time.perf_counter() - start) < DURATION:
        frame = capture.read_frame()
        if frame is None:
            time.sleep(0.5)
            continue

        frame_num += 1
        motion = motion_detector.detect(frame)

        if motion:
            motion_count += 1
            elapsed = time.perf_counter() - start
            print(f"  [{elapsed:5.1f}s] ✅ Movimiento #{motion_count}")

            # Guardar frame con movimiento
            path = os.path.join(OUTPUT_DIR, f"motion_{motion_count:03d}.jpg")
            cv2.imwrite(path, frame)

            # Capturar frame fresco
            fresh = capture.read_frame()
            if fresh is None:
                fresh = frame

            # Aplicar crop ROI si está configurado
            if roi:
                yolo_input = crop_roi(fresh, roi)
            else:
                yolo_input = fresh

            # Guardar lo que va a ver YOLO
            crop_path = os.path.join(OUTPUT_DIR, f"yolo_input_{motion_count:03d}.jpg")
            cv2.imwrite(crop_path, yolo_input)

            # Ejecutar detector
            t0 = time.perf_counter()
            detections = detector.detect(yolo_input)
            yolo_time = time.perf_counter() - t0
            yolo_runs += 1

            if detections:
                yolo_detections += len(detections)
                classes = [f"{d.class_name}({d.confidence:.0%})" for d in detections]
                print(f"         → YOLO ({yolo_time:.2f}s): {', '.join(classes)}")

                # Guardar frame con anotaciones
                annotated = yolo_input.copy()
                for d in detections:
                    x1, y1, x2, y2 = d.bbox
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated, f"{d.class_name} {d.confidence:.0%}",
                                (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                det_path = os.path.join(OUTPUT_DIR, f"detection_{motion_count:03d}.jpg")
                cv2.imwrite(det_path, annotated)

                # Contar vehículos
                new = vehicle_counter.count(detections)
                if new:
                    vehicles_counted += sum(new.values())
                    print(f"         → Contados: {new}")
            else:
                print(f"         → YOLO ({yolo_time:.2f}s): nada detectado")

        time.sleep(0.5)

    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"  Duración: {DURATION}s")
    print(f"  Frames revisados: {frame_num}")
    print(f"  Movimientos detectados: {motion_count}")
    print(f"  YOLO ejecutado: {yolo_runs} veces")
    print(f"  Detecciones YOLO: {yolo_detections}")
    print(f"  Vehículos contados: {vehicles_counted}")
    print(f"  Conteo del día: {vehicle_counter.get_counts()}")
    print()
    print(f"  Imágenes en: {OUTPUT_DIR}")
    print(f"  scp john@100.116.21.109:{OUTPUT_DIR}/*.jpg .")

    capture.release()


if __name__ == "__main__":
    main()
