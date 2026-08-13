"""Diagnóstico: por qué no cuenta vehículos.

Ejecutar en el servidor:
    cd ~/vigilancia && source venv/bin/activate && python diagnostico.py

Muestra paso a paso qué está pasando con motion y YOLO.
"""

import time
import sys

from src.config import Settings
from src.capture import RTSPCapture
from src.detection import MotionDetector, YOLODetector
from src.tracking import VehicleCounter


def main():
    settings = Settings()
    settings.validate()

    print("=" * 60)
    print("DIAGNÓSTICO DE CONTEO DE VEHÍCULOS")
    print("=" * 60)
    print(f"RTSP: {'stream2' if 'stream2' in settings.RTSP_URL else 'stream1'}")
    print(f"YOLO_TARGET_CLASSES: {settings.YOLO_TARGET_CLASSES}")
    print(f"YOLO_CONFIDENCE: {settings.YOLO_CONFIDENCE}")
    print(f"MOTION_THRESHOLD: {settings.MOTION_THRESHOLD}")
    print(f"MOTION_MIN_AREA: {settings.MOTION_MIN_AREA}")
    print(f"CAPTURE_INTERVAL: {settings.CAPTURE_INTERVAL}")
    print()

    capture = RTSPCapture(settings.RTSP_URL)
    motion_detector = MotionDetector(
        threshold=settings.MOTION_THRESHOLD,
        min_area=settings.MOTION_MIN_AREA,
    )
    yolo_detector = YOLODetector(
        confidence_threshold=settings.YOLO_CONFIDENCE,
        target_classes=settings.YOLO_TARGET_CLASSES,
    )
    vehicle_counter = VehicleCounter(cooldown=10.0)

    time.sleep(2)  # Esperar al hilo de captura

    # TEST 1: ¿Llegan frames?
    print("=" * 60)
    print("TEST 1: ¿Llegan frames de la cámara?")
    print("=" * 60)
    frame = capture.read_frame()
    if frame is None:
        print("❌ NO llegan frames. Problema de conexión RTSP.")
        return
    print(f"✅ Frame recibido: {frame.shape[1]}x{frame.shape[0]}")
    print()

    # TEST 2: ¿Se detecta movimiento?
    print("=" * 60)
    print("TEST 2: ¿Se detecta movimiento? (20 intentos, 1s entre cada uno)")
    print("Mueve algo frente a la cámara...")
    print("=" * 60)
    motion_count = 0
    for i in range(20):
        frame = capture.read_frame()
        if frame is None:
            print(f"  [{i+1:2d}] Sin frame")
            time.sleep(1)
            continue

        motion = motion_detector.detect(frame)
        status = "✅ MOVIMIENTO" if motion else "  - sin movimiento"
        if motion:
            motion_count += 1
        print(f"  [{i+1:2d}] {status}")
        time.sleep(1)

    print(f"\nMovimientos detectados: {motion_count}/20")
    if motion_count == 0:
        print("❌ No se detectó movimiento. Posibles causas:")
        print("   - Umbral muy alto (probar MOTION_THRESHOLD=15)")
        print("   - Área mínima muy grande (probar MOTION_MIN_AREA=200)")
        print("   - La cámara no apunta a una zona con movimiento")
        print()
        print("Probando con umbral más bajo (threshold=10, min_area=200)...")
        motion_detector2 = MotionDetector(threshold=10, min_area=200)
        motion_count2 = 0
        for i in range(10):
            frame = capture.read_frame()
            if frame is None:
                time.sleep(1)
                continue
            motion = motion_detector2.detect(frame)
            if motion:
                motion_count2 += 1
                print(f"  [{i+1:2d}] ✅ MOVIMIENTO con umbral bajo")
            time.sleep(1)
        if motion_count2 > 0:
            print(f"\n→ Con umbral bajo SÍ detecta ({motion_count2}/10).")
            print("→ Recomendación: bajar MOTION_THRESHOLD a 15 en .env")
        else:
            print("\n→ Tampoco detecta con umbral bajo. Revisar cámara.")
    print()

    # TEST 3: ¿YOLO detecta vehículos? (forzar sin motion)
    print("=" * 60)
    print("TEST 3: YOLO directo (sin esperar movimiento)")
    print("Analizando 3 frames...")
    print("=" * 60)
    for i in range(3):
        frame = capture.read_frame()
        if frame is None:
            print(f"  [{i+1}] Sin frame")
            time.sleep(2)
            continue

        t0 = time.perf_counter()
        detections = yolo_detector.detect(frame)
        elapsed = time.perf_counter() - t0

        if detections:
            print(f"  [{i+1}] ✅ {len(detections)} detecciones ({elapsed:.2f}s):")
            for d in detections:
                print(f"       - {d.class_name} (id={d.class_id}, conf={d.confidence:.1%})")

            # Probar conteo
            new = vehicle_counter.count(detections)
            if new:
                print(f"       → Vehículos contados: {new}")
            else:
                print(f"       → No se contaron (cooldown o no son vehículos)")
        else:
            print(f"  [{i+1}] ❌ Nada detectado ({elapsed:.2f}s)")

        time.sleep(3)

    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Conteo actual del día: {vehicle_counter.get_counts()}")
    print(f"Target classes configuradas: {settings.YOLO_TARGET_CLASSES}")
    print(f"  0=persona, 2=carro, 3=moto, 5=bus, 7=camión, 16=perro")
    print()
    print("Si TEST 2 falla → problema de motion detection (bajar umbral)")
    print("Si TEST 3 falla → YOLO no ve vehículos (revisar ángulo cámara)")
    print("Si TEST 3 OK pero no cuenta → revisar cooldown o class_id")

    capture.release()


if __name__ == "__main__":
    main()
