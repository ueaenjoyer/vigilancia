"""Benchmark de rendimiento del sistema de vigilancia.

Ejecutar en el servidor:
    cd ~/vigilancia && source venv/bin/activate && python benchmark.py
"""

import time
import sys

from src.config import Settings
from src.capture import RTSPCapture
from src.detection import MotionDetector, YOLODetector


def benchmark_capture(capture, n_frames=30):
    """Mide FPS de captura (lectura del frame más reciente)."""
    print(f"\n{'='*60}")
    print(f"BENCHMARK: Captura RTSP ({n_frames} frames)")
    print(f"{'='*60}")

    # Esperar a que el hilo tenga un frame
    time.sleep(2)

    times = []
    for i in range(n_frames):
        t0 = time.perf_counter()
        frame = capture.read_frame()
        t1 = time.perf_counter()
        if frame is not None:
            times.append(t1 - t0)
            if i == 0:
                print(f"  Resolución del frame: {frame.shape[1]}x{frame.shape[0]}")
        time.sleep(0.01)  # Simular polling

    if times:
        avg = sum(times) / len(times)
        print(f"  Frames obtenidos: {len(times)}/{n_frames}")
        print(f"  Tiempo promedio read_frame(): {avg*1000:.2f} ms")
        print(f"  FPS teórico de lectura: {1/avg:.0f}")
    else:
        print("  ERROR: No se obtuvieron frames")
    return times


def benchmark_motion(capture, motion_detector, n_frames=30):
    """Mide tiempo de detección de movimiento."""
    print(f"\n{'='*60}")
    print(f"BENCHMARK: Detección de movimiento ({n_frames} frames)")
    print(f"{'='*60}")

    times = []
    motions_detected = 0
    for i in range(n_frames):
        frame = capture.read_frame()
        if frame is None:
            time.sleep(0.1)
            continue

        t0 = time.perf_counter()
        motion = motion_detector.detect(frame)
        t1 = time.perf_counter()
        times.append(t1 - t0)
        if motion:
            motions_detected += 1
        time.sleep(0.1)  # 10 fps polling

    if times:
        avg = sum(times) / len(times)
        print(f"  Frames procesados: {len(times)}")
        print(f"  Movimientos detectados: {motions_detected}/{len(times)}")
        print(f"  Tiempo promedio: {avg*1000:.2f} ms")
        print(f"  FPS con motion detect: {1/avg:.0f}")
    return times


def benchmark_yolo(capture, yolo_detector, n_frames=5):
    """Mide tiempo de inferencia YOLO."""
    print(f"\n{'='*60}")
    print(f"BENCHMARK: YOLO inferencia ({n_frames} frames)")
    print(f"{'='*60}")

    times = []
    total_detections = 0
    for i in range(n_frames):
        frame = capture.read_frame()
        if frame is None:
            time.sleep(1)
            continue

        t0 = time.perf_counter()
        detections = yolo_detector.detect(frame)
        t1 = time.perf_counter()
        elapsed = t1 - t0
        times.append(elapsed)
        n_det = len(detections) if detections else 0
        total_detections += n_det
        classes = [d.class_name for d in detections] if detections else []
        print(f"  Frame {i+1}: {elapsed:.2f}s - {n_det} detecciones {classes}")

    if times:
        avg = sum(times) / len(times)
        mn = min(times)
        mx = max(times)
        print(f"\n  Resumen YOLO:")
        print(f"    Promedio: {avg:.2f}s")
        print(f"    Mínimo:   {mn:.2f}s")
        print(f"    Máximo:   {mx:.2f}s")
        print(f"    FPS YOLO: {1/avg:.2f}")
        print(f"    Total detecciones: {total_detections}")
    return times


def benchmark_pipeline(capture, motion_detector, yolo_detector, duration=30):
    """Simula el pipeline completo durante N segundos."""
    print(f"\n{'='*60}")
    print(f"BENCHMARK: Pipeline completo ({duration}s)")
    print(f"{'='*60}")

    start = time.perf_counter()
    frames_checked = 0
    motions = 0
    yolo_runs = 0
    detections_total = 0

    while (time.perf_counter() - start) < duration:
        frame = capture.read_frame()
        if frame is None:
            time.sleep(0.5)
            continue

        frames_checked += 1
        motion = motion_detector.detect(frame)

        if motion:
            motions += 1
            # Frame fresco para YOLO
            fresh = capture.read_frame()
            if fresh is None:
                fresh = frame
            dets = yolo_detector.detect(fresh)
            yolo_runs += 1
            if dets:
                detections_total += len(dets)

    elapsed = time.perf_counter() - start
    print(f"  Duración real: {elapsed:.1f}s")
    print(f"  Frames revisados: {frames_checked}")
    print(f"  Movimientos detectados: {motions}")
    print(f"  Veces que corrió YOLO: {yolo_runs}")
    print(f"  Detecciones totales: {detections_total}")
    print(f"  FPS efectivo del pipeline: {frames_checked/elapsed:.2f}")


def main():
    settings = Settings()
    settings.validate()

    print("Iniciando benchmark del sistema de vigilancia...")
    print(f"RTSP URL: {'stream2' if 'stream2' in settings.RTSP_URL else 'stream1'}")

    capture = RTSPCapture(settings.RTSP_URL)
    motion_detector = MotionDetector(
        threshold=settings.MOTION_THRESHOLD,
        min_area=settings.MOTION_MIN_AREA,
    )
    yolo_detector = YOLODetector(
        confidence_threshold=settings.YOLO_CONFIDENCE,
        target_classes=settings.YOLO_TARGET_CLASSES,
    )

    try:
        benchmark_capture(capture, n_frames=30)
        benchmark_motion(capture, motion_detector, n_frames=30)
        benchmark_yolo(capture, yolo_detector, n_frames=5)
        benchmark_pipeline(capture, motion_detector, yolo_detector, duration=30)
    finally:
        capture.release()

    print(f"\n{'='*60}")
    print("BENCHMARK COMPLETO")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
