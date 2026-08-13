"""Listener de comandos de Telegram vía polling (getUpdates).

Permite enviar comandos al bot desde el chat y recibir respuestas.
Comandos soportados:
    /foto - Captura una imagen en vivo de la cámara y la envía.
    /estado - Muestra el estado del sistema.
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
    """

    def __init__(self, bot_token: str, chat_id: str, capture):
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.capture = capture
        self._base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._offset = 0
        self._running = False
        self._thread: threading.Thread | None = None

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
        """Loop de polling que consulta getUpdates cada 2 segundos."""
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
            # Mover el offset para no recibir los mismos mensajes
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

        if text == "/foto":
            self._cmd_foto(chat_id)
        elif text == "/estado":
            self._cmd_estado(chat_id)
        elif text.startswith("/"):
            self._send_text(
                chat_id,
                "Comandos disponibles:\n/foto - Captura en vivo\n/estado - Estado del sistema",
            )

    def _cmd_foto(self, chat_id: str):
        """Captura un frame y lo envía como foto."""
        logger.info("Comando /foto recibido.")

        frame = self.capture.read_frame()
        if frame is None:
            self._send_text(chat_id, "⚠️ No se pudo capturar imagen de la cámara.")
            return

        # Agregar timestamp al frame
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

        # Codificar a JPEG
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            self._send_text(chat_id, "⚠️ Error al codificar imagen.")
            return

        # Enviar foto
        url = f"{self._base_url}/sendPhoto"
        files = {"photo": ("captura.jpg", buffer.tobytes(), "image/jpeg")}
        data = {"chat_id": chat_id, "caption": f"📷 Captura en vivo - {timestamp}"}

        try:
            response = requests.post(url, data=data, files=files, timeout=10)
            if response.status_code == 200:
                logger.info("Foto enviada por comando /foto.")
            else:
                logger.error("Error enviando foto: %s", response.text)
        except requests.RequestException as e:
            logger.error("Error de red enviando foto: %s", e)

    def _cmd_estado(self, chat_id: str):
        """Envía info del estado del sistema."""
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        uptime = time.time() - psutil.boot_time()
        hours = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)

        msg = (
            f"📊 Estado del sistema:\n"
            f"• CPU: {cpu}%\n"
            f"• RAM: {mem.used // (1024*1024)}MB / {mem.total // (1024*1024)}MB ({mem.percent}%)\n"
            f"• Uptime: {hours}h {mins}m\n"
            f"• Cámara: {'✅ Conectada' if self.capture.read_frame() is not None else '❌ Desconectada'}"
        )
        self._send_text(chat_id, msg)

    def _send_text(self, chat_id: str, text: str):
        """Envía un mensaje de texto."""
        url = f"{self._base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, data=data, timeout=10)
        except requests.RequestException as e:
            logger.error("Error enviando texto: %s", e)
