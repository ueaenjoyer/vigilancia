"""Diagnóstico largo (2 minutos) con guardado de imágenes.

Ejecutar:
    python diagnostico2.py

Guarda imágenes en /tmp/vigilancia_debug/ cuando detecta movimiento
y ejecuta YOLO sobre ellas. También guarda 3 frames al inicio para
verificar qué ve la cámara.
"""

import os
import time

import cv2
import numpy as np

from src.config import Settings
from src.capture import RTSPCapture
from src.detection import MotionDetector, YOLODetector
from src.tracking import VehicleCounter

OUTPUT_DIR = "/tmp/vigilancia_debug"
DURATION = 120  # 2 minutos


def main():
    settings = Settings()
    settings.validate()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print(f"DIAGNÓSTICO LARGO ({DURATION}s)")
    print(f"Imágenes se guardan en: {OUTPUT_DIR}")
    print("=" * 60)
    print(f"RTSP: {'stream2' if 'stream2' in settings.RTSP_URL else 'stream1'}")
    print(f"YOLO_TARGET_CLASSES: {settings.YOLO_TARGET_CLASSES}")
    print(f"YOLO_CONFIDENCE: {settings.YOLO_CONFIDENCE}")
    print()

    capture = RTSPCapture(settings.RTSP_URL)
    motion_detector = MotionDetector(
        threshold=settings.MOTION_THRESHOLD,
        min_area=settings.MOTION_MIN_AREA,
    )
    yolo_detector = YOLODetector(
        confidence_threshold=0.3,  # Umbral más bajo para ver más
        target_classes=settings.YOLO_TARGET_CLASSES,
    )
    vehicle_counter = VehicleCounter(cooldown=10.0)

    time.sleep(2)

    # Guardar 3 frames iniciales para ver qué ve la cámara
    print("Guardando 3 frames de referencia...")
    for i in range(3):
        frame = capture.read_frame()
        if frame is not None:
            path = os.path.join(OUTPUT_DIR, f"referencia_{i+1}.jpg")
            cv2.imwrite(path, frame)
            print(f"  → {path}")
        time.sleep(1)

    print()
    print(f"Monitoreando por {DURATION} segundos... (pasan carros por la calle?)")
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

            # Ejecutar YOLO
            fresh = capture.read_frame()
            if fresh is None:
                fresh = frame
            t0 = time.perf_counter()
            detections = yolo_detector.detect(fresh)
            yolo_time = time.perf_counter() - t0
            yolo_runs += 1

            if detections:
                yolo_detections += len(detections)
                classes = [f"{d.class_name}({d.confidence:.0%})" for d in detections]
                print(f"         → YOLO ({yolo_time:.2f}s): {', '.join(classes)}")

                # Guardar frame con anotaciones
                annotated = fresh.copy()
                for d in detections:
                    x1, y1, x2, y2 = d.bbox
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated, f"{d.class_name} {d.confidence:.0%}",
                                (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
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
    print(f"  Imágenes guardadas en: {OUTPUT_DIR}")
    print(f"  Para ver las imágenes:")
    print(f"    scp john@server-john:{OUTPUT_DIR}/*.jpg .")
    print()

    if motion_count > 0 and yolo_detections == 0:
        print("⚠️  YOLO no detectó nada a pesar de haber movimiento.")
        print("   Posibles causas:")
        print("   - Carros muy lejos/pequeños para YOLOv8n a 640x360")
        print("   - Ángulo de cámara no ideal (muy oblicuo)")
        print("   - Confianza muy alta (ya bajé a 0.3 para este test)")
        print()
        print("   Descarga las imágenes para verificar qué ve la cámara.")

    capture.release()


if __name__ == "__main__":
    main()
