"""Módulo de captura RTSP para cámaras IP.

Usa un hilo dedicado para mantener siempre el frame más reciente
disponible, evitando acumulación en el buffer RTSP.

Ejemplo de URL para cámaras Tapo:
    rtsp://usuario:contraseña@ip:554/stream2
"""

import time
import logging
import threading

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Constantes de reconexión
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 60.0
_BACKOFF_FACTOR = 2.0


class RTSPCapture:
    """Captura frames de un stream RTSP con reconexión automática.

    Usa un hilo dedicado que lee frames continuamente del buffer RTSP,
    manteniendo siempre el frame más reciente disponible. Esto elimina
    la latencia causada por acumulación en el buffer.

    Parámetros
    ----------
    rtsp_url : str
        URL completa del stream RTSP.
        Ejemplo: rtsp://usuario:contraseña@192.168.1.100:554/stream2
    """

    def __init__(self, rtsp_url: str) -> None:
        self._url = rtsp_url
        self._cap: cv2.VideoCapture | None = None
        self._backoff = _INITIAL_BACKOFF_S

        # Frame más reciente (protegido por lock)
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        self._connect()
        self._start_reader()

    # ------------------------------------------------------------------
    # Hilo de lectura continua
    # ------------------------------------------------------------------

    def _start_reader(self) -> None:
        """Inicia el hilo que lee frames continuamente."""
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        logger.info("Hilo de captura RTSP iniciado.")

    def _reader_loop(self) -> None:
        """Lee frames continuamente, manteniendo siempre el más reciente."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self._reconnect()
                if self._cap is None or not self._cap.isOpened():
                    time.sleep(1)
                    continue

            try:
                ret, frame = self._cap.read()
            except Exception:
                logger.exception("Error leyendo frame del stream RTSP.")
                self._reconnect()
                continue

            if not ret or frame is None:
                logger.warning("Frame no disponible, reconectando.")
                self._reconnect()
                continue

            # Actualizar el frame más reciente
            with self._lock:
                self._frame = frame

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Abre la conexión al stream RTSP con buffer mínimo."""
        logger.info("Conectando al stream RTSP: %s", self._safe_url())
        try:
            self._cap = cv2.VideoCapture(self._url)
            # Buffer mínimo para reducir latencia
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self._cap.isOpened():
                logger.info("Conexión RTSP establecida.")
                self._backoff = _INITIAL_BACKOFF_S
            else:
                logger.warning("No se pudo abrir el stream RTSP.")
                self._cap.release()
                self._cap = None
        except Exception:
            logger.exception("Error al conectar al stream RTSP.")
            self._cap = None

    def _reconnect(self) -> None:
        """Reconexión con backoff exponencial (máximo 60 s)."""
        self._release_internal()
        logger.info("Reintentando conexión en %.1f s...", self._backoff)
        time.sleep(self._backoff)
        self._connect()
        if self._cap is None or not self._cap.isOpened():
            self._backoff = min(self._backoff * _BACKOFF_FACTOR, _MAX_BACKOFF_S)

    # ------------------------------------------------------------------
    # Lectura de frames
    # ------------------------------------------------------------------

    def read_frame(self) -> np.ndarray | None:
        """Retorna el frame más reciente capturado.

        Returns
        -------
        numpy.ndarray | None
            Frame en formato BGR (OpenCV) o None si no hay frame disponible.
        """
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    # ------------------------------------------------------------------
    # Liberación de recursos
    # ------------------------------------------------------------------

    def _release_internal(self) -> None:
        """Libera el VideoCapture interno."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                logger.exception("Error liberando VideoCapture.")
            finally:
                self._cap = None

    def release(self) -> None:
        """Libera todos los recursos de captura."""
        logger.info("Liberando recursos de captura RTSP.")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._release_internal()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "RTSPCapture":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _safe_url(self) -> str:
        """Oculta credenciales de la URL para logging seguro."""
        try:
            if "@" in self._url:
                scheme_and_creds, rest = self._url.split("@", 1)
                scheme = scheme_and_creds.split("://")[0]
                return f"{scheme}://***:***@{rest}"
        except Exception:
            pass
        return "<url>"
