"""Test: ¿Los frames cambian entre sí?

Verifica si el hilo de captura entrega frames diferentes
o siempre el mismo frame congelado.

Ejecutar:
    python test_frames.py
"""

import time
import cv2
import numpy as np

from src.config import Settings
from src.capture import RTSPCapture


def main():
    settings = Settings()
    settings.validate()

    print("Conectando a RTSP...")
    capture = RTSPCapture(settings.RTSP_URL)
    time.sleep(3)  # Esperar a que el hilo tenga frames

    print(f"URL: {'stream2' if 'stream2' in settings.RTSP_URL else 'stream1'}")
    print()

    # TEST A: ¿Los frames son objetos diferentes?
    print("=" * 60)
    print("TEST A: ¿Los frames cambian entre lecturas?")
    print("=" * 60)

    frames = []
    for i in range(5):
        f = capture.read_frame()
        if f is not None:
            frames.append(f)
            print(f"  Frame {i+1}: shape={f.shape}, mean={f.mean():.2f}")
        else:
            print(f"  Frame {i+1}: None!")
        time.sleep(1)

    if len(frames) >= 2:
        print()
        for i in range(1, len(frames)):
            diff = cv2.absdiff(frames[i], frames[i-1])
            diff_sum = diff.sum()
            diff_mean = diff.mean()
            identical = np.array_equal(frames[i], frames[i-1])
            print(f"  Frame {i} vs {i+1}: identical={identical}, diff_mean={diff_mean:.4f}, diff_sum={diff_sum}")

        if all(np.array_equal(frames[i], frames[i-1]) for i in range(1, len(frames))):
            print()
            print("❌ TODOS los frames son IDÉNTICOS.")
            print("   El hilo de captura no está actualizando el frame,")
            print("   o el stream RTSP está congelado.")
            print()
            print("   Probando captura directa SIN hilo...")
            test_direct_capture(settings.RTSP_URL)
        else:
            print()
            print("✅ Los frames SÍ cambian entre sí.")
            print("   El motion detector debería funcionar.")
            print("   Posible problema: GaussianBlur + threshold eliminan diferencias pequeñas.")
    else:
        print("❌ No se obtuvieron suficientes frames.")

    capture.release()


def test_direct_capture(url):
    """Prueba captura directa sin el hilo, leyendo del buffer."""
    print()
    print("=" * 60)
    print("TEST B: Captura directa (sin hilo)")
    print("=" * 60)

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("❌ No se pudo abrir el stream.")
        return

    print(f"  Stream abierto. Backend: {cap.getBackendName()}")
    print(f"  FPS reportados: {cap.get(cv2.CAP_PROP_FPS)}")
    print(f"  Buffer size: {cap.get(cv2.CAP_PROP_BUFFERSIZE)}")
    print()

    frames = []
    for i in range(5):
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
            print(f"  Frame {i+1}: shape={frame.shape}, mean={frame.mean():.2f}")
        else:
            print(f"  Frame {i+1}: read() falló (ret={ret})")
        time.sleep(1)

    if len(frames) >= 2:
        print()
        for i in range(1, len(frames)):
            diff = cv2.absdiff(frames[i], frames[i-1])
            identical = np.array_equal(frames[i], frames[i-1])
            print(f"  Frame {i} vs {i+1}: identical={identical}, diff_mean={diff.mean():.4f}")

        if not all(np.array_equal(frames[i], frames[i-1]) for i in range(1, len(frames))):
            print()
            print("✅ Captura directa SÍ tiene frames diferentes.")
            print("   → El problema está en el hilo de captura (RTSPCapture).")
        else:
            print()
            print("❌ Captura directa también da frames idénticos.")
            print("   → El stream RTSP está congelado o la cámara no envía frames nuevos.")
            print("   → Probar reiniciar la cámara o usar stream1.")

    cap.release()


if __name__ == "__main__":
    main()
