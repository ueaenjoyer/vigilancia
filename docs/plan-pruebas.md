# Plan de Pruebas

## Objetivo

Validar que el sistema cumple con los KPIs definidos y funciona correctamente en escenarios reales antes de desplegarlo como solucion de seguridad.

---

## KPIs del sistema

| Indicador | Meta | Metodo de medicion |
|-----------|------|--------------------|
| CPU promedio | < 40% | `vmstat`, `htop`, script de monitoreo |
| RAM | < 350 MB | `free -m`, monitoreo continuo |
| Temperatura | < 65 C | `/sys/class/thermal/thermal_zone0/temp` |
| Eventos detectados | > 95% | Escenarios controlados con eventos conocidos |
| Falsos positivos | < 5% | Conteo manual vs eventos detectados |
| Consumo electrico | < 3 W | Medidor USB (ej: USB Doctor) |

---

## Fases de prueba

### Fase 1: Rendimiento base

**Objetivo:** Establecer la linea base de la Raspberry Pi Zero 2 W sin carga de trabajo.

**Pruebas:**

| # | Prueba | Comando/Herramienta | Resultado esperado |
|---|--------|--------------------|--------------------|
| 1.1 | CPU en reposo | `vmstat 1 60` | < 5% uso |
| 1.2 | RAM en reposo | `free -m` | > 300 MB libres |
| 1.3 | Temperatura en reposo | `cat /sys/class/thermal/thermal_zone0/temp` | < 45 C |
| 1.4 | Velocidad escritura SD | `dd if=/dev/zero of=test bs=1M count=100` | > 10 MB/s |
| 1.5 | Velocidad escritura USB | `dd if=/dev/zero of=/mnt/usb/test bs=1M count=100` | > 20 MB/s |
| 1.6 | Throughput Wi-Fi | `iperf3 -c <servidor>` | > 20 Mbps |
| 1.7 | Latencia red local | `ping -c 100 <camara>` | < 10 ms avg |

**Script:** `tests/benchmarks/baseline.sh`

---

### Fase 2: Red y conectividad

**Objetivo:** Verificar estabilidad de la conexion Wi-Fi con la camara.

**Pruebas:**

| # | Prueba | Duracion | Resultado esperado |
|---|--------|----------|--------------------|
| 2.1 | Stream RTSP estable | 1 hora | 0 desconexiones |
| 2.2 | Stream bajo carga | 1 hora (con deteccion activa) | < 2 desconexiones |
| 2.3 | Reconexion automatica | Simular corte Wi-Fi | Reconecta < 30 s |
| 2.4 | Ancho de banda sostenido | 1 hora | Estable +/- 10% |
| 2.5 | Interferencia 2.4 GHz | Hora pico (muchos dispositivos) | Stream sin cortes |

**Script:** `tests/benchmarks/network.sh`

---

### Fase 3: Almacenamiento

**Objetivo:** Comparar rendimiento entre microSD y disco USB.

**Pruebas:**

| # | Prueba | microSD | USB HDD | USB SSD |
|---|--------|---------|---------|---------|
| 3.1 | Escritura secuencial | ? MB/s | ? MB/s | ? MB/s |
| 3.2 | Lectura secuencial | ? MB/s | ? MB/s | ? MB/s |
| 3.3 | Escritura aleatoria 4K | ? MB/s | ? MB/s | ? MB/s |
| 3.4 | CPU durante escritura | ?% | ?% | ?% |
| 3.5 | Estabilidad 24h | OK/FAIL | OK/FAIL | OK/FAIL |

**Script:** `tests/benchmarks/storage.sh`

---

### Fase 4: Captura de video

**Objetivo:** Determinar el intervalo optimo de muestreo de frames.

**Pruebas:**

| # | Intervalo | CPU | RAM | Frames/min | Detecciones |
|---|-----------|-----|-----|------------|-------------|
| 4.1 | 1 frame / 5 s | ? | ? | 12 | ? |
| 4.2 | 1 frame / 3 s | ? | ? | 20 | ? |
| 4.3 | 1 FPS | ? | ? | 60 | ? |
| 4.4 | 2 FPS | ? | ? | 120 | ? |
| 4.5 | 5 FPS | ? | ? | 300 | ? |

**Duracion de cada prueba:** 30 minutos con escenario controlado.

**Script:** `tests/benchmarks/capture.sh`

---

### Fase 5: Detector de movimiento

**Objetivo:** Calibrar parametros del detector y medir rendimiento.

**Pruebas:**

| # | Prueba | Metrica | Meta |
|---|--------|---------|------|
| 5.1 | Tiempo por frame (640x480) | ms | < 50 ms |
| 5.2 | Tiempo por frame (1280x720) | ms | < 100 ms |
| 5.3 | CPU durante deteccion | % | < 15% |
| 5.4 | RAM durante deteccion | MB | < 50 MB adicionales |
| 5.5 | Tasa de deteccion correcta | % | > 95% |
| 5.6 | Tasa de falsos positivos | % | < 5% |

**Parametros a calibrar:**

- `blur_kernel`: 15, 21, 31
- `threshold`: 15, 20, 25, 30, 35
- `min_area_pct`: 0.5%, 1.0%, 2.0%, 3.0%
- `cooldown_s`: 3, 5, 10

**Script:** `tests/benchmarks/detection.sh`

---

## Escenarios de prueba reales

### Ubicacion

Escenarios grabados en el area de vigilancia real (exterior/interior segun instalacion).

### Lista de escenarios

| # | Escenario | Resultado esperado | Prioridad |
|---|-----------|-------------------|-----------|
| E1 | Persona caminando (dia) | Detectado | Alta |
| E2 | Persona corriendo (dia) | Detectado | Alta |
| E3 | Persona caminando (noche) | Detectado | Alta |
| E4 | Abrir puerta/porton | Detectado | Alta |
| E5 | Vehiculo entrando | Detectado | Alta |
| E6 | Encender/apagar luz | NO detectado (o ignorado) | Media |
| E7 | Mascota pequena | Configurable (ignorar o detectar) | Media |
| E8 | Mascota grande | Detectado | Media |
| E9 | Movimiento de arboles/plantas | NO detectado | Alta |
| E10 | Lluvia | NO detectado | Alta |
| E11 | Sombras moviles (nubes) | NO detectado | Media |
| E12 | Insectos frente a camara | NO detectado | Baja |
| E13 | Cambio brusco de luz (amanecer) | NO detectado | Media |

**Carpeta de evidencia:** `tests/scenarios/`

**Formato:**

```
tests/scenarios/
  E01_persona_caminando_dia/
    video.mp4
    resultado_esperado.txt
    resultado_obtenido.txt
  E02_persona_corriendo_dia/
    ...
```

---

## Pruebas de estabilidad

| # | Prueba | Duracion | Criterio de exito |
|---|--------|----------|-------------------|
| S1 | Funcionamiento continuo | 24 horas | Sin crash, sin memory leak |
| S2 | Funcionamiento continuo | 72 horas | Sin degradacion de rendimiento |
| S3 | Ciclo dia/noche completo | 24 horas | Detecciones correctas en ambos |
| S4 | Sin Internet 24h | 24 horas | Grabacion y deteccion local OK |
| S5 | Disco lleno | Hasta llenar | Rotacion correcta, sin crash |
| S6 | Reconexion camara | 10 cortes simulados | Reconecta siempre < 30 s |

---

## Pruebas de alarma (GPIO)

| # | Prueba | Resultado esperado |
|---|--------|--------------------|
| G1 | Evento detectado -> GPIO HIGH | Pin activo en < 1 s |
| G2 | Cooldown respetado | No re-activacion durante cooldown |
| G3 | Multiples eventos rapidos | Solo 1 activacion por cooldown |
| G4 | Rele conectado | Central recibe senal |
| G5 | Pin liberado tras timeout | GPIO LOW tras N segundos |

---

## Herramientas de monitoreo

| Herramienta | Uso |
|-------------|-----|
| `htop` | Monitoreo interactivo CPU/RAM |
| `vmstat` | Estadisticas de sistema |
| `iotop` | Monitoreo de I/O a disco |
| `iperf3` | Throughput de red |
| `vcgencmd measure_temp` | Temperatura GPU/SoC |
| `free -m` | Uso de memoria |
| Script custom | Logging continuo a CSV |

---

## Registro de resultados

Cada prueba debe registrarse con:

1. Fecha y hora.
2. Version del software.
3. Parametros de configuracion.
4. Resultado numerico.
5. Observaciones.

**Formato sugerido:** CSV o JSON en `tests/benchmarks/results/`.

---

## Criterio de aceptacion global

El sistema se considera listo para produccion cuando:

- [ ] Todas las pruebas de Fase 1-5 completadas.
- [ ] KPIs dentro de meta durante 72 horas continuas.
- [ ] Escenarios E1-E5 detectados con > 95% de exito.
- [ ] Escenarios E9-E10 con < 5% de falsos positivos.
- [ ] Prueba de estabilidad S2 (72h) superada.
- [ ] Alarma GPIO funcional (G1-G5 OK).
