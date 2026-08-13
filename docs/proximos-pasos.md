# Proximos Pasos

## Estado actual: Planificacion

Fecha de inicio: 2026-08-06

---

## Fase 0: Preparacion del hardware

**Objetivo:** Tener todo el hardware listo y funcional.

- [ ] Identificar el modelo exacto de la camara Xiaomi.
- [ ] Verificar si el modelo soporta RTSP nativo.
  - Si no: investigar firmware alternativo (ej: yi-hack, Xiaomi-Dafang-Hacks).
- [ ] Obtener la URL del stream RTSP.
- [ ] Verificar resolucion y FPS disponibles via RTSP.
- [ ] Conseguir microSD para la Raspberry (minimo 32 GB, clase A1/A2).
- [ ] Conseguir adaptador USB OTG + hub (para disco externo).
- [ ] Conseguir disco USB (HDD o SSD) para almacenamiento.
- [ ] Conseguir fuente de alimentacion 5V 2.5A para la Pi.

---

## Fase 1: Configuracion base de la Raspberry Pi

**Objetivo:** Sistema operativo funcional con acceso remoto.

- [x] Descargar Raspberry Pi OS Lite (64-bit).
- [x] Flashear imagen con Raspberry Pi Imager.
  - Configurar Wi-Fi durante el flasheo.
  - Habilitar SSH durante el flasheo.
  - Establecer usuario y contrasena.
- [ ] Primer arranque y verificar conectividad.
- [ ] Conectar por SSH.
- [ ] Actualizar sistema: `sudo apt update && sudo apt upgrade`.
- [ ] Configurar hostname (ej: `vigilancia`).
- [ ] Configurar IP estatica (opcional pero recomendado).
- [ ] Configurar autenticacion SSH por clave (deshabilitar contrasena).
- [ ] Instalar herramientas basicas: `htop`, `iotop`, `vim`, `git`.

---

## Fase 2: Medicion de rendimiento base

**Objetivo:** Conocer los limites reales del hardware.

- [ ] Medir CPU, RAM y temperatura en reposo.
- [ ] Medir velocidad de escritura de la microSD.
- [ ] Conectar disco USB y medir velocidad de escritura.
- [ ] Medir throughput Wi-Fi con iperf3.
- [ ] Medir latencia hacia la camara (ping).
- [ ] Documentar resultados en `tests/benchmarks/results/`.

**Referencia:** [Plan de pruebas - Fase 1](plan-pruebas.md#fase-1-rendimiento-base)

---

## Fase 3: Captura de video

**Objetivo:** Recibir y guardar el stream RTSP de la camara.

- [ ] Instalar FFmpeg: `sudo apt install ffmpeg`.
- [ ] Probar conexion manual al stream RTSP.
  ```bash
  ffmpeg -i rtsp://<ip_camara>:<puerto>/stream -t 10 test.mp4
  ```
- [ ] Verificar que el video se graba correctamente.
- [ ] Implementar segmentacion automatica (archivos de 60s).
  ```bash
  ffmpeg -i rtsp://... -c copy -f segment -segment_time 60 \
    -strftime 1 /grabaciones/%Y%m%d_%H%M%S.mp4
  ```
- [ ] Implementar script Python para gestionar la captura (`src/capture/`).
- [ ] Medir CPU y RAM durante captura continua.
- [ ] Probar estabilidad durante 1 hora.
- [ ] Implementar reconexion automatica ante caida del stream.

---

## Fase 4: Deteccion de movimiento

**Objetivo:** Detectar actividad en la escena con bajo consumo de CPU.

- [ ] Instalar OpenCV headless: `pip install opencv-python-headless`.
- [ ] Implementar extraccion de frames desde los segmentos de video.
- [ ] Implementar algoritmo de diferencia de frames (`src/detection/`).
- [ ] Configurar parametros iniciales (blur, threshold, min_area).
- [ ] Probar con escenarios controlados (persona caminando).
- [ ] Medir CPU y RAM durante deteccion.
- [ ] Calibrar umbrales para minimizar falsos positivos.
- [ ] Implementar sistema de cooldown entre eventos.
- [ ] Integrar deteccion con captura (pipeline completo).

---

## Fase 5: Gestion de almacenamiento

**Objetivo:** Rotacion automatica y priorizacion de grabaciones.

- [ ] Definir estructura de carpetas de grabaciones.
  ```
  /grabaciones/YYYY/MM/DD/cam01_YYYYMMDD_HHMMSS.mp4
  ```
- [ ] Implementar modulo de gestion de espacio (`src/storage/`).
- [ ] Implementar politica de retencion:
  - Con evento: conservar 30 dias.
  - Sin evento: conservar 24-72 horas.
- [ ] Implementar limpieza automatica cuando el disco alcance 90%.
- [ ] Probar escenario de disco lleno (rotacion correcta).
- [ ] Implementar metadatos de segmentos (SQLite o JSON).

---

## Fase 6: Integracion con alarma

**Objetivo:** Activar GPIO ante eventos criticos.

- [ ] Instalar gpiozero: `pip install gpiozero`.
- [ ] Implementar modulo de alarma (`src/alarm/`).
- [ ] Probar activacion de GPIO con LED (sin rele).
- [ ] Conectar rele optoacoplado al GPIO.
- [ ] Verificar que la central de alarma recibe la senal.
- [ ] Implementar logica de activacion/desactivacion.
- [ ] Implementar timeout de pin (volver a LOW tras N segundos).
- [ ] Probar escenario completo: deteccion -> GPIO -> central -> sirena.

---

## Fase 7: Modo online (futuro)

**Objetivo:** Enviar frames a servicio de IA cuando hay Internet.

- [ ] Implementar verificacion de conectividad (`src/network/`).
- [ ] Definir API o servicio de IA a utilizar.
- [ ] Implementar envio de frames para clasificacion.
- [ ] Implementar recepcion de resultados.
- [ ] Implementar notificaciones (Telegram como primera opcion).
- [ ] Implementar cola de eventos para envio diferido.
- [ ] Probar transicion online/offline sin perder datos.

---

## Fase 8: Servicio y produccion

**Objetivo:** Sistema funcionando como servicio autonomo.

- [ ] Crear servicio systemd para el pipeline principal.
- [ ] Configurar inicio automatico al arrancar.
- [ ] Configurar reinicio automatico ante fallos.
- [ ] Implementar logging estructurado.
- [ ] Implementar monitoreo de salud (watchdog).
- [ ] Prueba de estabilidad 72 horas.
- [ ] Documentar procedimiento de instalacion.
- [ ] Documentar procedimiento de mantenimiento.

---

## Ideas futuras (sin prioridad definida)

- [ ] IA local usando laptop antigua.
- [ ] Reconocimiento de personas conocidas.
- [ ] Reconocimiento de vehiculos.
- [ ] OCR de placas vehiculares.
- [ ] Integracion con Home Assistant.
- [ ] Panel web para revision de eventos.
- [ ] Cifrado de grabaciones (LUKS).
- [ ] NAS distribuido (multiples nodos).
- [ ] Sincronizacion automatica cuando vuelva Internet.
- [ ] Notificaciones por multiples canales (email, push, SMS).
- [ ] Backup automatico a la nube.
- [ ] Modo timelapse para revision rapida.

---

## Notas importantes

1. **No avanzar a la siguiente fase sin completar las mediciones de la fase actual.** Cada decision debe estar respaldada por datos.

2. **Documentar todo.** Cada prueba, cada resultado, cada decision. El proyecto debe ser reproducible.

3. **Commits frecuentes.** Cada funcionalidad completa merece un commit con mensaje descriptivo.

4. **Principio de simplicidad.** Si algo funciona con un script de 20 lineas, no crear un framework de 500.
