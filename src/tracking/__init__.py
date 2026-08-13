"""Contador de vehículos por tipo con persistencia diaria.

Lleva un registro de vehículos detectados clasificados por tipo,
con reset automático a medianoche y persistencia en JSON.
"""

import json
import logging
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Directorio de datos persistentes
_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Mapeo de class_id a tipo de vehículo
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Emojis por tipo
VEHICLE_EMOJI = {
    "car": "🚗",
    "motorcycle": "🏍️",
    "bus": "🚌",
    "truck": "🚛",
}


class VehicleCounter:
    """Contador de vehículos con cooldown por tipo para evitar doble conteo.

    Args:
        cooldown: Segundos mínimos entre conteos del mismo tipo.
            Evita contar el mismo vehículo varias veces mientras pasa.
        data_dir: Directorio donde guardar los datos JSON.
    """

    def __init__(self, cooldown: float = 10.0, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or _DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._cooldown = cooldown
        self._last_count_time: Dict[str, float] = {}  # tipo -> timestamp último conteo
        self._today: str = ""
        self._counts: Dict[str, int] = {}  # tipo -> cantidad hoy

        # Cargar datos del día actual
        self._load_today()

    # ------------------------------------------------------------------
    # Conteo
    # ------------------------------------------------------------------

    def count(self, detections: List) -> Dict[str, int]:
        """Procesa detecciones y cuenta vehículos nuevos.

        Solo cuenta un vehículo si pasó el cooldown desde el último
        conteo del mismo tipo (evita contar el mismo vehículo 3 veces
        mientras cruza el campo de visión).

        Args:
            detections: Lista de Detection del YOLO detector.

        Returns:
            Dict con los vehículos nuevos contados en esta llamada.
            Ej: {"car": 1, "motorcycle": 1}
        """
        self._check_day_reset()

        now = time.time()
        new_counts: Dict[str, int] = {}

        for det in detections:
            if det.class_id not in VEHICLE_CLASSES:
                continue

            vehicle_type = VEHICLE_CLASSES[det.class_id]

            # Verificar cooldown
            last_time = self._last_count_time.get(vehicle_type, 0)
            if (now - last_time) < self._cooldown:
                continue

            # Contar
            self._counts[vehicle_type] = self._counts.get(vehicle_type, 0) + 1
            self._last_count_time[vehicle_type] = now
            new_counts[vehicle_type] = new_counts.get(vehicle_type, 0) + 1

            logger.info(
                "Vehículo contado: %s (total hoy: %d)",
                vehicle_type,
                self._counts[vehicle_type],
            )

        # Guardar si hubo cambios
        if new_counts:
            self._save()

        return new_counts

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def get_today_summary(self) -> str:
        """Retorna resumen del conteo de hoy formateado para Telegram."""
        self._check_day_reset()

        total = sum(self._counts.values())

        if total == 0:
            return "📊 Conteo de vehículos hoy:\n\nNo se han detectado vehículos aún."

        lines = [f"📊 Conteo de vehículos — {self._today}\n"]

        for vehicle_type in ["car", "motorcycle", "bus", "truck"]:
            count = self._counts.get(vehicle_type, 0)
            if count > 0:
                emoji = VEHICLE_EMOJI.get(vehicle_type, "🚗")
                name = self._type_name(vehicle_type)
                lines.append(f"  {emoji} {name}: {count}")

        lines.append(f"\n  Total: {total} vehículos")
        lines.append(f"  Cooldown: {self._cooldown}s entre conteos")

        return "\n".join(lines)

    def get_counts(self) -> Dict[str, int]:
        """Retorna el dict de conteos del día actual."""
        self._check_day_reset()
        return self._counts.copy()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _get_file_path(self, day: str) -> Path:
        """Ruta del archivo JSON para un día dado."""
        return self._data_dir / f"vehicles_{day}.json"

    def _load_today(self) -> None:
        """Carga los datos del día actual desde JSON."""
        self._today = date.today().isoformat()
        filepath = self._get_file_path(self._today)

        if filepath.exists():
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                self._counts = data.get("counts", {})
                logger.info("Datos de conteo cargados para %s: %s", self._today, self._counts)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Error cargando datos de conteo: %s", e)
                self._counts = {}
        else:
            self._counts = {}

    def _save(self) -> None:
        """Guarda los datos del día actual en JSON."""
        filepath = self._get_file_path(self._today)
        data = {
            "date": self._today,
            "counts": self._counts,
            "last_updated": datetime.now().isoformat(),
        }
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Error guardando datos de conteo: %s", e)

    def _check_day_reset(self) -> None:
        """Resetea contadores si cambió el día."""
        today = date.today().isoformat()
        if today != self._today:
            logger.info("Nuevo día detectado (%s → %s). Reset de contadores.", self._today, today)
            self._today = today
            self._counts = {}
            self._last_count_time = {}

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _type_name(vehicle_type: str) -> str:
        """Nombre en español del tipo de vehículo."""
        names = {
            "car": "Carros",
            "motorcycle": "Motos",
            "bus": "Buses",
            "truck": "Camiones",
        }
        return names.get(vehicle_type, vehicle_type)
