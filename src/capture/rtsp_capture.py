"""Módulo de captura RTSP para cámaras IP.

Ejemplo de URL para cámaras Tapo:
    rtsp://usuario:contraseña@ip:554/stream2
"""

import time
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Constantes de reconexión
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 60.0
_BACKOFF_FACTOR = 2.0


class RTSPCapture:
    """Captura frames de un stream RTSP con reconexión automática.

    Parámetros
    ----------
    rtsp_url : str
        URL completa del stream RTSP.
        Ejemplo: rtsp://usuario:contraseña@192.168.1.100:554/stream2

    Uso como context manager::

        with RTSPCapture("rtsp://...") as cap:
            frame = cap.read_frame()
    """

    def __init__(self, rtsp_url: str) -> None:
        self._url = rtsp_url
        self._cap: cv2.VideoCapture | None = None
        self._backoff = _INITIAL_BACKOFF_S
        self._connect()

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Abre la conexión al stream RTSP."""
        logger.info("Conectando al stream RTSP: %s", self._safe_url())
        try:
            self._cap = cv2.VideoCapture(self._url)
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
        logger.info(
            "Reintentando conexión en %.1f s...", self._backoff
        )
        time.sleep(self._backoff)
        self._connect()
        # Incrementar backoff para el próximo intento si sigue fallando
        if self._cap is None or not self._cap.isOpened():
            self._backoff = min(self._backoff * _BACKOFF_FACTOR, _MAX_BACKOFF_S)

    # ------------------------------------------------------------------
    # Lectura de frames
    # ------------------------------------------------------------------

    def read_frame(self) -> np.ndarray | None:
        """Lee un frame del stream RTSP.

        Returns
        -------
        numpy.ndarray | None
            Frame en formato BGR (OpenCV) o None si no se pudo leer.
        """
        if self._cap is None or not self._cap.isOpened():
            self._reconnect()
            if self._cap is None or not self._cap.isOpened():
                return None

        try:
            ret, frame = self._cap.read()
        except Exception:
            logger.exception("Error leyendo frame del stream RTSP.")
            self._reconnect()
            return None

        if not ret or frame is None:
            logger.warning("Frame no disponible, iniciando reconexión.")
            self._reconnect()
            return None

        return frame

    # ------------------------------------------------------------------
    # Liberación de recursos
    # ------------------------------------------------------------------

    def _release_internal(self) -> None:
        """Libera el VideoCapture interno sin log de cierre final."""
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
        self._release_internal()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "RTSPCapture":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.release()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _safe_url(self) -> str:
        """Oculta credenciales de la URL para logging seguro."""
        try:
            # rtsp://user:pass@host:port/path -> rtsp://***:***@host:port/path
            if "@" in self._url:
                scheme_and_creds, rest = self._url.split("@", 1)
                scheme = scheme_and_creds.split("://")[0]
                return f"{scheme}://***:***@{rest}"
        except Exception:
            pass
        return "<url>"
