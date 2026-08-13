# NAS via SMB - Camaras Xiaomi Mi Home

## Descubrimiento

Las camaras Xiaomi Mi Home tienen soporte nativo para enviar grabaciones a un NAS mediante protocolo **SMB 1.0**. Esto elimina la necesidad de capturar el stream RTSP para obtener los videos.

---

## Como funciona

```
Camara Xiaomi Mi Home
        |
        | SMB 1.0 (Wi-Fi)
        v
Carpeta compartida (Windows/Linux/Raspberry Pi)
        |
        v
Videos almacenados localmente
```

La camara **empuja** los archivos de video a la carpeta compartida de forma automatica. No es necesario que un cliente se conecte a la camara.

---

## Configuracion en Windows (referencia)

### 1. Crear usuario local

- Crear cuenta de usuario local (sin cuenta Microsoft).
- Asignar permisos de Administrador.

### 2. Crear carpeta compartida

- Crear carpeta en un disco secundario (no C:).
- Configurar permisos: "Everyone" con lectura y escritura.
- Compartir la carpeta en la red.

### 3. Habilitar SMB 1.0

- Panel de control > Programas > Activar o desactivar caracteristicas de Windows.
- Marcar "SMB 1.0/CIFS File Sharing Support".
- Reiniciar.

### 4. Configurar en la app Mi Home

1. Abrir app > seleccionar camara > Manage Storage.
2. Seleccionar "NAS network storage".
3. La app detecta el dispositivo en la red.
4. Ingresar usuario y contrasena.
5. Seleccionar carpeta.
6. Configurar frecuencia: "Immediately" (recomendado).
7. Configurar periodo de retencion.

---

## Configuracion en Raspberry Pi (objetivo)

La Raspberry Pi puede actuar como servidor SMB usando **Samba**.

### Instalacion

```bash
sudo apt install samba samba-common-bin
```

### Configuracion basica (`/etc/samba/smb.conf`)

```ini
[vigilancia]
   path = /mnt/usb/grabaciones
   browseable = yes
   writeable = yes
   guest ok = no
   create mask = 0775
   directory mask = 0775
   valid users = vigilancia
```

### Crear usuario Samba

```bash
sudo useradd -M -s /sbin/nologin vigilancia
sudo smbpasswd -a vigilancia
```

### Habilitar SMB 1.0 (requerido por la camara)

En `/etc/samba/smb.conf`, seccion `[global]`:

```ini
[global]
   min protocol = NT1
   server min protocol = NT1
```

**Nota de seguridad:** SMB 1.0 es un protocolo antiguo con vulnerabilidades conocidas. Mitigacion: la red debe ser local y aislada, sin exposicion a Internet.

### Reiniciar Samba

```bash
sudo systemctl restart smbd
sudo systemctl enable smbd
```

---

## Implicaciones para la arquitectura

### Ventajas

| Aspecto | Beneficio |
|---------|-----------|
| Simplicidad | No requiere FFmpeg ni captura RTSP |
| Estabilidad | La camara gestiona la grabacion, no la Pi |
| CPU | Casi cero carga (solo recibe archivos) |
| Compatibilidad | Funcionalidad nativa de la camara |
| Confiabilidad | La camara tiene buffer interno si la red falla |

### Desventajas

| Aspecto | Riesgo |
|---------|--------|
| SMB 1.0 | Protocolo inseguro (mitigar con red aislada) |
| Latencia | Los archivos llegan con retraso (no es tiempo real) |
| Control | No controlas la segmentacion del video |
| Formato | Dependes del formato que la camara genere |

### Cambio en el flujo

**Antes (RTSP):**
```
Camara -> RTSP -> Pi captura -> Pi segmenta -> Pi guarda
```

**Ahora (SMB):**
```
Camara -> SMB -> Pi recibe archivos ya segmentados
```

La Pi pasa de ser un capturador activo a un **receptor pasivo** de archivos.

---

## Arquitectura revisada

```
Camara Xiaomi Mi Home
        |
        | SMB 1.0 (push automatico)
        v
+----------------------------------+
| Raspberry Pi Zero 2 W (Samba)   |
|                                  |
|  /mnt/usb/grabaciones/           |
|        |                         |
|        v                         |
|  +-------------+                 |
|  | Watcher     | (inotifywait)   |
|  | Nuevo archivo detectado       |
|  +-------------+                 |
|        |                         |
|        v                         |
|  +-------------+                 |
|  | Deteccion   |                 |
|  | movimiento  |                 |
|  +-------------+                 |
|        |                         |
|   Evento?                        |
|    /    \                        |
|   SI     NO                      |
|   |       |                      |
|   v       v                      |
| Alarma  Marcar para              |
| GPIO    rotacion futura          |
+----------------------------------+
```

---

## Nuevo flujo de deteccion

1. La camara graba y envia archivos a la Pi via SMB.
2. Un watcher (inotifywait / watchdog Python) detecta archivos nuevos.
3. Se extraen frames del archivo recibido.
4. Se ejecuta deteccion de movimiento sobre esos frames.
5. Si hay evento: marcar segmento como importante + activar alarma.
6. Si no hay evento: marcar para futura eliminacion.

---

## Investigacion pendiente

- [ ] Confirmar modelo exacto de la camara.
- [ ] Verificar que el modelo soporta NAS/SMB.
- [ ] Verificar formato de los archivos generados (MP4? H.264? H.265?).
- [ ] Verificar tamano y duracion de los segmentos.
- [ ] Verificar si la camara funciona con SMB en la Raspberry Pi (Samba).
- [ ] Probar frecuencia "Immediately" y medir retraso real.
- [ ] Verificar si la camara continua grabando a SD si el NAS no responde.

---

## Estrategia dual (recomendada)

Mantener ambas opciones disponibles:

| Metodo | Uso |
|--------|-----|
| SMB (NAS) | Metodo principal, bajo consumo, simple |
| RTSP | Backup, analisis en tiempo real (futuro), si SMB falla |

Esto alinea con el principio de resiliencia del proyecto.
