# Arquitectura del Sistema

## Vision general

El sistema opera como un NVR (Network Video Recorder) ligero sobre una Raspberry Pi Zero 2 W. La arquitectura esta disenada para funcionar de forma autonoma sin depender de servicios externos.

---

## Diagrama de componentes

```
+------------------------------------------------------------------+
|                        RASPBERRY PI ZERO 2 W                     |
|                                                                  |
|  +------------+    +-------------+    +-----------+              |
|  |  Captura   |--->|  Muestreo   |--->| Deteccion |              |
|  |   RTSP     |    |  de frames  |    | Movimiento|              |
|  +------------+    +-------------+    +-----------+              |
|        |                                    |                    |
|        v                                    v                    |
|  +------------+                       +-----------+              |
|  |  Storage   |                       |  Eventos  |              |
|  | (segmentos)|                       |  (log)    |              |
|  +------------+                       +-----------+              |
|        |                                    |                    |
|        v                                    v                    |
|  +------------+                       +-----------+              |
|  | Disco USB  |                       |   GPIO    |              |
|  |  / microSD |                       |   Rele    |              |
|  +------------+                       +-----------+              |
|                                             |                    |
+------------------------------------------------------------------+
                                              |
                                              v
                                     +----------------+
                                     | Central alarma |
                                     |    (sirena)    |
                                     +----------------+
```

---

## Componentes principales

### 1. Captura RTSP (`src/capture/`)

**Responsabilidad:** Conectar al stream RTSP de la camara Xiaomi y segmentar el video.

**Tecnologia probable:** FFmpeg (via subprocess o wrapper Python).

**Funcionamiento:**

1. Conectar al stream RTSP de la camara.
2. Segmentar en archivos de video cortos (ej: 60 segundos).
3. Nombrar archivos con timestamp para facilitar busqueda.
4. Notificar al modulo de almacenamiento.

**Formato de salida:**

```
/grabaciones/2026/08/06/
  cam01_20260806_143000.mp4
  cam01_20260806_143100.mp4
  ...
```

---

### 2. Muestreo de frames

**Responsabilidad:** Extraer frames del stream a un intervalo configurable para analisis.

**Configuracion por defecto:**

| Parametro | Valor |
|-----------|-------|
| Intervalo | 1 FPS |
| Resolucion | Original o reducida |
| Formato | JPEG (en memoria) |

**Justificacion de 1 FPS:**

- Una persona caminando a velocidad normal recorre ~1.4 m/s.
- En un campo de vision tipico (5-10 m), permanece visible 4-7 segundos.
- Con 1 FPS se obtienen 4-7 capturas del evento.
- Suficiente para detectar y registrar.

---

### 3. Deteccion de movimiento (`src/detection/`)

**Responsabilidad:** Determinar si hay actividad significativa en la escena.

**Algoritmo: Diferencia absoluta de frames**

```
1. Convertir frame a escala de grises
2. Aplicar desenfoque gaussiano (reducir ruido)
3. Calcular diferencia absoluta con frame anterior
4. Aplicar umbral binario
5. Calcular porcentaje de pixeles activos
6. Si porcentaje > umbral --> EVENTO
```

**Parametros configurables:**

| Parametro | Valor por defecto | Descripcion |
|-----------|-------------------|-------------|
| blur_kernel | 21 | Tamano del kernel gaussiano |
| threshold | 25 | Umbral de binarizacion (0-255) |
| min_area_pct | 1.0% | Porcentaje minimo de area en movimiento |
| cooldown_s | 5 | Segundos entre eventos consecutivos |

**Ventajas:**

- Muy bajo consumo de CPU.
- No requiere GPU ni modelos de IA.
- Funciona en la Pi Zero 2 W sin problemas.

**Limitaciones:**

- No distingue tipo de objeto (persona vs animal vs arbol).
- Sensible a cambios de iluminacion.
- Requiere calibracion de umbrales por escena.

---

### 4. Almacenamiento (`src/storage/`)

**Responsabilidad:** Gestionar el espacio en disco, rotacion y limpieza de grabaciones.

**Estrategia:**

```
Segmento grabado
      |
      v
 Tiene evento? --SI--> Conservar (alta prioridad)
      |
      NO
      |
      v
 Conservar temporalmente (baja prioridad)
      |
      v
 Espacio bajo? --SI--> Eliminar segmentos antiguos sin eventos
```

**Politicas de retencion:**

| Tipo | Retencion |
|------|-----------|
| Con evento | 30 dias (configurable) |
| Sin evento | 24-72 horas (configurable) |
| Critico (alarma activada) | Indefinido hasta revision manual |

**Almacenamiento estimado (1 camara, H.264, 720p):**

| Calidad | Bitrate | Por hora | Por dia |
|---------|---------|----------|---------|
| Baja | 500 kbps | ~225 MB | ~5.4 GB |
| Media | 1 Mbps | ~450 MB | ~10.8 GB |
| Alta | 2 Mbps | ~900 MB | ~21.6 GB |

---

### 5. Alarma / GPIO (`src/alarm/`)

**Responsabilidad:** Activar salida GPIO cuando se detecta un evento critico.

**Integracion:**

```
Evento detectado (deteccion)
        |
        v
   GPIO pin HIGH
        |
        v
  Rele optoacoplado
        |
        v
 Entrada de zona (central alarma)
        |
        v
 Central activa sirena (segun su logica)
```

**Importante:** La Raspberry NO controla la sirena directamente. Solo actua como un sensor mas dentro del sistema de alarma existente. La central se encarga de:

- Alimentacion de respaldo (bateria).
- Temporizadores de entrada/salida.
- Activacion de sirena.
- Logica de armado/desarmado.

**Pin GPIO sugerido:** GPIO17 (configurable).

---

### 6. Red / Conectividad (`src/network/`)

**Responsabilidad:** Gestionar la comunicacion con servicios externos cuando hay Internet disponible.

**Funciones:**

- Verificar conectividad periodicamente.
- Enviar frames a servicio de IA (modo online).
- Recibir clasificaciones.
- Enviar notificaciones (Telegram, push, etc.).
- Sincronizar eventos con servidor remoto.

**Comportamiento segun estado de red:**

| Estado | Accion |
|--------|--------|
| Online | Enviar frames a IA + notificaciones |
| Offline | Solo deteccion local + alarma GPIO |
| Intermitente | Cola de eventos, envio cuando sea posible |

---

## Flujo de datos completo

```
Camara Xiaomi
     |
     | RTSP stream (Wi-Fi 2.4 GHz)
     v
+-----------------------+
| Modulo Captura        |
| - Recibe stream       |
| - Segmenta video      |
| - Extrae frames (1fps)|
+-----------------------+
     |            |
     |            v
     |    +-----------------+
     |    | Mod. Deteccion  |
     |    | - Diff frames   |
     |    | - Umbral        |
     |    | - Evento?       |
     |    +-----------------+
     |            |
     |       SI   |   NO
     |       |    |    |
     |       v    |    v
     |   +------+ | (descarta frame)
     |   |Evento| |
     |   +------+ |
     |       |    |
     v       v    |
+------------------+
| Mod. Storage     |
| - Guarda segmento|
| - Marca prioridad|
| - Rota antiguos  |
+------------------+
     
     Evento?
       |
       v
+------------------+       +------------------+
| Mod. Alarma      |       | Mod. Red         |
| - GPIO HIGH      |       | - Enviar a IA    |
| - Rele activo    |       | - Notificacion   |
+------------------+       +------------------+
```

---

## Tecnologias candidatas

| Componente | Opcion principal | Alternativa |
|------------|-----------------|-------------|
| Lenguaje | Python 3 | C (para critico) |
| Captura RTSP | FFmpeg | GStreamer |
| Procesamiento de imagen | OpenCV (headless) | Pillow |
| GPIO | gpiozero | RPi.GPIO |
| Almacenamiento | Sistema de archivos | SQLite (metadatos) |
| Configuracion | YAML / TOML | JSON |
| Logs | logging (stdlib) | systemd journal |
| Servicio | systemd | supervisor |

---

## Consideraciones de recursos

### Raspberry Pi Zero 2 W - Limitaciones

| Recurso | Disponible | Nota |
|---------|-----------|------|
| CPU | 4 cores ARM Cortex-A53 @ 1 GHz | Compartido con OS |
| RAM | 512 MB | ~350 MB usable |
| GPU | VideoCore IV | No util para CV |
| Wi-Fi | 2.4 GHz 802.11n | ~30-50 Mbps real |
| USB | 1x micro-USB (OTG) | Requiere hub/adaptador |
| GPIO | 40 pines | Compartido con HATs |

### Presupuesto de CPU estimado

| Proceso | CPU estimado |
|---------|-------------|
| FFmpeg (captura + segmentacion) | 15-25% |
| Muestreo de frames | 2-5% |
| Deteccion de movimiento | 5-10% |
| Escritura a disco | 3-5% |
| Sistema operativo | 5-10% |
| **Total estimado** | **30-55%** |

**Margen de seguridad:** Si el total supera 60%, reducir FPS de muestreo o calidad de video.

---

## Seguridad

- Las grabaciones se almacenan en formato estandar (MP4/H.264).
- Cifrado de disco completo (futuro): LUKS en disco USB.
- Acceso SSH con autenticacion por clave (sin contrasena).
- Firewall local (iptables/nftables) permitiendo solo trafico necesario.
- Sin puertos expuestos a Internet.

---

## Escalabilidad futura

| Fase | Descripcion |
|------|-------------|
| 1 camara | Implementacion actual |
| 2-3 camaras | Requiere evaluar ancho de banda Wi-Fi |
| IA local | Laptop antigua como servidor de inferencia |
| Multi-nodo | Varias Raspberry Pi con almacenamiento centralizado |
| Panel web | Interfaz para revision de eventos |
