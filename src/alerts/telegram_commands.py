"""Listener de comandos de Telegram vía polling (getUpdates).

Permite enviar comandos al bot desde el chat y recibir respuestas.
Comandos soportados:
    /foto       - Captura una imagen en vivo de la cámara y la envía.
    /test       - Fuerza detección YOLO y muestra resultados con scores.
    /estado     - Muestra el estado del sistema.
    /conteo     - Muestra conteo de vehículos del día.
    /pausa      - Pausa las alertas automáticas.
    /reanudar   - Reanuda las alertas automáticas.
    /sensibilidad [alta|media|baja] - Cambia el umbral de movimiento.
"""

import logging
import threading
import time

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)


class TelegramCommands:
    """Escucha comandos del bot de Telegram vía long-polling.

    Corre en un hilo aparte para no bloquear el loop principal.

    Args:
        bot_token: Token del bot de Telegram.
        chat_id: ID del chat autorizado (solo responde a este).
        capture: Instancia de RTSPCapture para tomar fotos.
        yolo_detector: Instancia de YOLODetector para /test.
        motion_detector: Instancia de MotionDetector para /sensibilidad.
    """

    def __init__(self, bot_token: str, chat_id: str, capture, yolo_detector=None, motion_detector=None, vehicle_counter=None):
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.capture = capture
        self.yolo_detector = yolo_detector
        self.motion_detector = motion_detector
        self.vehicle_counter = vehicle_counter
        self._base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._offset = 0
        self._running = False
        self._thread: threading.Thread | None = None

        # Estado de pausa (accesible desde main.py)
        self.alertas_pausadas = False

    def start(self):
        """Inicia el listener en un hilo daemon."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Listener de comandos Telegram iniciado.")

    def stop(self):
        """Detiene el listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Listener de comandos Telegram detenido.")

    def _poll_loop(self):
        """Loop de polling que consulta getUpdates."""
        while self._running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._handle_update(update)
            except requests.RequestException as e:
                logger.warning("Error de red en polling de comandos: %s", e)
                time.sleep(5)
            except Exception as e:
                logger.error("Error en polling de comandos: %s", e)
                time.sleep(5)

            time.sleep(2)

    def _get_updates(self) -> list:
        """Obtiene nuevos mensajes del bot via getUpdates."""
        url = f"{self._base_url}/getUpdates"
        params = {
            "offset": self._offset,
            "timeout": 10,
            "allowed_updates": '["message"]',
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()

        if not data.get("ok"):
            return []

        updates = data.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1

        return updates

    def _handle_update(self, update: dict):
        """Procesa un update recibido."""
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()

        # Solo responder al chat autorizado
        if chat_id != self.chat_id:
            logger.warning("Mensaje de chat no autorizado: %s", chat_id)
            return

        # Parsear comando
        cmd = text.split()[0].lower() if text else ""
        args = text.split()[1:] if text else []

        if cmd == "/foto":
            self._cmd_foto(chat_id)
        elif cmd == "/test":
            self._cmd_test(chat_id)
        elif cmd == "/estado":
            self._cmd_estado(chat_id)
        elif cmd == "/conteo":
            self._cmd_conteo(chat_id)
        elif cmd == "/pausa":
            self._cmd_pausa(chat_id)
        elif cmd == "/reanudar":
            self._cmd_reanudar(chat_id)
        elif cmd == "/sensibilidad":
            self._cmd_sensibilidad(chat_id, args)
        elif cmd.startswith("/"):
            self._send_text(
                chat_id,
                "📋 Comandos disponibles:\n"
                "/foto - Captura en vivo\n"
                "/test - Forzar detección YOLO\n"
                "/estado - Estado del sistema\n"
                "/conteo - Conteo de vehículos hoy\n"
                "/pausa - Pausar alertas\n"
                "/reanudar - Reanudar alertas\n"
                "/sensibilidad [alta|media|baja] - Cambiar sensibilidad",
            )

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------

    def _cmd_foto(self, chat_id: str):
        """Captura un frame y lo envía como foto."""
        logger.info("Comando /foto recibido.")

        frame = self.capture.read_frame()
        if frame is None:
            self._send_text(chat_id, "⚠️ No se pudo capturar imagen de la cámara.")
            return

        # Agregar timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        self._send_photo(chat_id, frame, f"📷 Captura en vivo - {timestamp}")

    def _cmd_test(self, chat_id: str):
        """Fuerza detección YOLO y muestra resultados detallados."""
        logger.info("Comando /test recibido.")

        if self.yolo_detector is None:
            self._send_text(chat_id, "⚠️ Detector YOLO no disponible.")
            return

        frame = self.capture.read_frame()
        if frame is None:
            self._send_text(chat_id, "⚠️ No se pudo capturar imagen de la cámara.")
            return

        self._send_text(chat_id, "🔍 Analizando imagen con YOLO... (puede tardar ~5s)")

        # Forzar detección con umbral bajo para ver todo
        original_conf = self.yolo_detector.confidence_threshold
        self.yolo_detector.confidence_threshold = 0.2  # Umbral bajo para ver más
        detections = self.yolo_detector.detect(frame)
        self.yolo_detector.confidence_threshold = original_conf

        if not detections:
            # Enviar foto sin anotaciones
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            self._send_photo(chat_id, frame, "❌ No se detectó nada (umbral: 0.2)")
            return

        # Dibujar detecciones en el frame
        annotated = frame.copy()
        results_text = "🎯 Detecciones encontradas:\n\n"

        for i, det in enumerate(detections, 1):
            x1, y1, x2, y2 = det.bbox
            color = (0, 255, 0) if det.class_name == "persona" else (255, 0, 0)

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name} {det.confidence:.0%}"
            cv2.putText(annotated, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            results_text += f"{i}. {det.class_name} — confianza: {det.confidence:.1%}\n"

        results_text += f"\nUmbral normal: {original_conf:.0%}"
        results_text += f"\nUmbral test: 20%"

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(annotated, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        self._send_photo(chat_id, annotated, results_text)

    def _cmd_estado(self, chat_id: str):
        """Envía info del estado del sistema."""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            uptime = time.time() - psutil.boot_time()
            hours = int(uptime // 3600)
            mins = int((uptime % 3600) // 60)

            # Estado de la cámara
            frame = self.capture.read_frame()
            cam_status = "✅ Conectada" if frame is not None else "❌ Desconectada"

            # Sensibilidad actual
            sens = "desconocida"
            if self.motion_detector:
                th = self.motion_detector.threshold
                if th <= 15:
                    sens = f"alta (umbral={th})"
                elif th <= 30:
                    sens = f"media (umbral={th})"
                else:
                    sens = f"baja (umbral={th})"

            msg = (
                f"📊 Estado del sistema:\n"
                f"• CPU: {cpu}%\n"
                f"• RAM: {mem.used // (1024*1024)}MB / {mem.total // (1024*1024)}MB ({mem.percent}%)\n"
                f"• Uptime: {hours}h {mins}m\n"
                f"• Cámara: {cam_status}\n"
                f"• Alertas: {'⏸️ PAUSADAS' if self.alertas_pausadas else '▶️ Activas'}\n"
                f"• Sensibilidad: {sens}"
            )
            self._send_text(chat_id, msg)

        except ImportError:
            self._send_text(chat_id, "⚠️ psutil no instalado. Ejecuta: pip install psutil")

    def _cmd_pausa(self, chat_id: str):
        """Pausa las alertas automáticas."""
        self.alertas_pausadas = True
        logger.info("Alertas pausadas por comando /pausa.")
        self._send_text(chat_id, "⏸️ Alertas pausadas. Usa /reanudar para reactivar.")

    def _cmd_reanudar(self, chat_id: str):
        """Reanuda las alertas automáticas."""
        self.alertas_pausadas = False
        logger.info("Alertas reanudadas por comando /reanudar.")
        self._send_text(chat_id, "▶️ Alertas reactivadas.")

    def _cmd_sensibilidad(self, chat_id: str, args: list):
        """Cambia la sensibilidad de detección de movimiento."""
        if not self.motion_detector:
            self._send_text(chat_id, "⚠️ Detector de movimiento no disponible.")
            return

        niveles = {
            "alta": 15,
            "media": 25,
            "baja": 40,
        }

        if not args or args[0].lower() not in niveles:
            actual = self.motion_detector.threshold
            self._send_text(
                chat_id,
                f"Uso: /sensibilidad [alta|media|baja]\n\n"
                f"• alta — detecta movimientos sutiles (umbral=15)\n"
                f"• media — balance normal (umbral=25)\n"
                f"• baja — solo movimientos grandes (umbral=40)\n\n"
                f"Actual: umbral={actual}",
            )
            return

        nivel = args[0].lower()
        nuevo_umbral = niveles[nivel]
        self.motion_detector.threshold = nuevo_umbral
        logger.info("Sensibilidad cambiada a '%s' (umbral=%d).", nivel, nuevo_umbral)
        self._send_text(chat_id, f"✅ Sensibilidad: {nivel} (umbral={nuevo_umbral})")

    def _cmd_conteo(self, chat_id: str):
        """Muestra el conteo de vehículos del día."""
        logger.info("Comando /conteo recibido.")

        if self.vehicle_counter is None:
            self._send_text(chat_id, "⚠️ Contador de vehículos no disponible.")
            return

        summary = self.vehicle_counter.get_today_summary()
        self._send_text(chat_id, summary)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send_photo(self, chat_id: str, frame: np.ndarray, caption: str):
        """Codifica y envía una foto."""
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            self._send_text(chat_id, "⚠️ Error al codificar imagen.")
            return

        url = f"{self._base_url}/sendPhoto"
        files = {"photo": ("captura.jpg", buffer.tobytes(), "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption}

        try:
            response = requests.post(url, data=data, files=files, timeout=15)
            if response.status_code == 200:
                logger.info("Foto enviada por comando.")
            else:
                logger.error("Error enviando foto: %s", response.text)
        except requests.RequestException as e:
            logger.error("Error de red enviando foto: %s", e)

    def _send_text(self, chat_id: str, text: str):
        """Envía un mensaje de texto."""
        url = f"{self._base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, data=data, timeout=10)
        except requests.RequestException as e:
            logger.error("Error enviando texto: %s", e)
