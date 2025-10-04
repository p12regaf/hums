¡Por supuesto! Prepararé una documentación técnica completa en formato Markdown. Este documento está diseñado para que cualquier persona con conocimientos básicos de Linux y Python pueda entender no solo **qué hace** el sistema, sino **por qué se diseñó de esta manera**, y cómo puede replicarlo, mantenerlo y extenderlo.

---

# Sistema HUMS: Documentación Técnica Completa

## 1. Introducción y Filosofía del Proyecto

### 1.1. ¿Qué es el Sistema HUMS?

El **Health and Usage Monitoring System (HUMS)** es una plataforma integral de adquisición y procesamiento de datos para vehículos, basada en una Raspberry Pi. Su objetivo es registrar, procesar y presentar información crítica sobre el estado y el uso de un vehículo, incluyendo:

*   **Datos del motor y del sistema (OBD-II):** RPM, velocidad, temperatura, códigos de error (DTCs), etc.
*   **Datos de telemetría:** Posicionamiento GPS y mediciones de la Unidad de Medición Inercial (IMU).
*   **Información de identificación:** Número de bastidor (VIN) y número de verificación de calibración (CVN).

El sistema está diseñado para funcionar de forma autónoma, iniciando automáticamente al arrancar el vehículo y gestionando los datos de forma robusta.

### 1.2. La Arquitectura: De Scripts Aislados a una Aplicación Unificada

La versión original del proyecto consistía en múltiples scripts de Python, cada uno lanzado por un servicio de `systemd` diferente. Este enfoque, aunque funcional, presentaba serios inconvenientes:

*   **Falta de Cohesión:** Los scripts no se comunicaban entre sí y no compartían un estado común.
*   **Complejidad de Gestión:** Administrar 5-6 servicios diferentes es propenso a errores.
*   **Dificultad para Depurar:** Un fallo en un script no era visible para los demás.
*   **Consumo de Recursos:** Múltiples bucles `while True` para monitorizar GPIO consumían ciclos de CPU innecesariamente.

La arquitectura refactorizada se basa en una filosofía de **Aplicación Unificada y Modular**:

> **Un único punto de entrada (`main.py`) orquesta una colección de módulos especializados, cada uno con una responsabilidad única. Todo el sistema es gestionado por un único servicio (`hums_app.service`).**

Esto nos proporciona:
*   **Modularidad:** Cada pieza (Logger OBD, GUI, Servidor Web) es una clase independiente y reutilizable.
*   **Control Centralizado:** La GUI actúa como un panel de control que puede iniciar y detener los servicios de fondo.
*   **Eficiencia:** Se utilizan técnicas modernas como hilos (threading) para tareas en segundo plano y detección de eventos por interrupción para GPIO, liberando la CPU.
*   **Mantenibilidad:** Una configuración centralizada (`config.py`) y una estructura de carpetas lógica hacen que el proyecto sea fácil de entender y modificar.

## 2. Estructura del Proyecto

La organización de los ficheros es fundamental para la claridad del proyecto.

```
/home/cosigein/hums_project/
├── main.py                 # Punto de entrada principal. Orquesta la aplicación.
├── config.py               # Fichero central de configuración (rutas, pines, etc.).
|
├── src/                    # Código fuente de la aplicación.
│   ├── core/               # Módulos con la lógica de negocio principal.
│   │   ├── obd_logger.py       # Clase para registrar datos CAN/OBD.
│   │   ├── gps_imu_logger.py   # Clase para registrar datos del sensor GPS/IMU.
│   │   └── log_processor.py    # Funciones para procesar logs con DBC.
│   │
│   ├── services/           # Módulos que proveen servicios (web, hardware).
│   │   ├── gpio_monitor.py   # Clase para monitorizar pines GPIO con interrupciones.
│   │   └── web_server.py     # Clase para el servidor web de archivos.
│   │
│   └── gui/                # Interfaz Gráfica de Usuario (GUI).
│       └── app.py              # Clase principal de la aplicación Tkinter.
│
├── assets/                 # Recursos estáticos.
│   ├── dbc/
│   │   └── CSS-Electronics-11-bit-OBD2-v2.1.dbc
│   ├── config_files/
│   │   └── solicitudes.csv
│   └── templates/
│       └── web_server_template.html
│
├── data/                   # Directorio (creado automáticamente) para datos generados.
│   ├── can_logs/           
│   ├── csv_exports/        
│   ├── imu_gps_logs/       
│   └── system_logs/        
│
├── tools/                  # Scripts de utilidad para el desarrollador.
│   └── generate_documentation.py
│
├── hums_app.service        # Fichero de unidad para systemd.
└── README.md
```

## 3. Análisis Detallado de Componentes

### 3.1. El Orquestador (`main.py` y `config.py`)

*   **`config.py`:** Es el cerebro de la configuración. En lugar de tener rutas de archivos o números de pin repartidos por todo el código, se definen como constantes en este único lugar. Esto significa que si mueves una carpeta o cambias un pin, solo tienes que modificar este archivo. También incluye una función `setup_directories()` que crea la estructura de carpetas de `data/` si no existe.
*   **`main.py`:** Su única responsabilidad es iniciar la aplicación. Primero llama a `config.setup_directories()` para preparar el entorno y luego instancia y lanza la clase `Application` de la GUI. Es el punto de partida que `systemd` utiliza.

### 3.2. Módulos del Núcleo (`src/core/`)

Estos módulos contienen la lógica principal de adquisición y procesamiento de datos. Han sido diseñados como **clases controlables** que se ejecutan en hilos separados.

*   **`OBDLogger` (`obd_logger.py`):**
    *   **Propósito:** Gestionar el registro de datos del bus CAN.
    *   **Funcionamiento:** Al llamarse a `start()`, inicia un hilo que configura la interfaz CAN (`can0`), lanza un subproceso `candump` para capturar todo el tráfico y guardarlo en un archivo de log diario, y entra en un bucle que envía solicitudes OBD-II (leídas desde `solicitudes.csv`) a intervalos definidos.
    *   **Diseño:** El uso de `threading` es crucial para que el registro no bloquee la interfaz gráfica. El método `stop()` permite una detención limpia, terminando el subproceso `candump` y desactivando la interfaz CAN.

*   **`GPSIMULogger` (`gps_imu_logger.py`):**
    *   **Propósito:** Leer datos del sensor GPS/IMU conectado por puerto serie.
    *   **Funcionamiento:** Similar al `OBDLogger`, su método `start()` lanza un hilo. Este hilo intenta conectar con el puerto serie definido en `config.py`, crea un archivo CSV de log organizado por `AÑO/MES/DIA.csv`, y entra en un bucle leyendo líneas del puerto serie y escribiéndolas en el CSV.
    *   **Diseño:** Incluye una lógica robusta para manejar la desconexión del dispositivo serie, intentando reconectar automáticamente. También gestiona la rotación de archivos de log cada día.

*   **Procesador de Logs (`log_processor.py`):**
    *   **Propósito:** Convertir los archivos de log CAN en bruto (`.log`) a un formato legible y útil (`.csv`) utilizando un archivo DBC.
    *   **Funcionamiento:** La función `process_pending_logs()` escanea la carpeta `can_logs/`, la compara con una lista de archivos ya procesados (`processed_files.txt`), y para cada nuevo log, lo lee línea por línea, decodifica las tramas CAN con la librería `cantools` y el archivo `.dbc`, y escribe los resultados en un nuevo archivo CSV.
    *   **Diseño:** Se ha creado una clase interna `OBDDataExtractor` para manejar la decodificación de mensajes multi-trama (como el VIN), evitando el uso de variables globales y haciendo el proceso más limpio.

### 3.3. Módulos de Servicios (`src/services/`)

Estos módulos proporcionan funcionalidades de apoyo.

*   **`GPIOMonitor` (`gpio_monitor.py`):**
    *   **Propósito:** Reaccionar a eventos físicos, como un botón de apagado.
    *   **Funcionamiento:** En lugar de un bucle `while True` que consume CPU, este módulo utiliza la funcionalidad de **interrupciones** de la librería `RPi.GPIO` (`GPIO.add_event_detect`). Configura los pines para que el hardware de la Raspberry Pi le "avise" solo cuando el estado de un pin cambia.
    *   **Diseño:** Una vez iniciado, consume prácticamente cero CPU mientras espera un evento. Cuando se detecta el evento de apagado, ejecuta el comando `sudo shutdown now`.

*   **`WebServer` (`web_server.py`):**
    *   **Propósito:** Ofrecer una interfaz web simple para acceder a los archivos CSV generados.
    *   **Funcionamiento:** Utiliza las librerías estándar de Python para crear un servidor HTTP en un hilo. Sirve una página HTML (cargada desde `assets/templates/`) que lista los archivos del directorio `csv_exports/` con opciones para descargar, subir y eliminar.
    *   **Diseño:** La separación del HTML en un archivo de plantilla (`.html`) del código Python que lo sirve es una práctica estándar que mejora enormemente la mantenibilidad.

### 3.4. La Interfaz Gráfica (`src/gui/app.py`)

*   **Propósito:** Actuar como el centro de control para el usuario.
*   **Funcionamiento:** Es una aplicación `tkinter`. Al iniciarse, crea instancias de todos los módulos de lógica (`OBDLogger`, `WebServer`, etc.). Los botones de la interfaz no contienen la lógica en sí, sino que simplemente llaman a los métodos de estas instancias (ej. `self.obd_logger.start()`).
*   **Diseño:** Este es el patrón **Controlador**. La GUI controla la lógica, pero no la implementa. Esto mantiene el código de la interfaz limpio y enfocado en la presentación, mientras que la lógica compleja reside en sus propios módulos. Implementa una función `on_closing` para asegurarse de que todos los hilos de fondo se detengan de forma segura cuando el usuario cierra la ventana.

## 4. Flujo de Datos

El flujo de información en el sistema es el siguiente:

1.  **Adquisición:**
    *   `OBDLogger` lee datos del bus CAN -> Guarda en `data/can_logs/canlog_YYYYMMDD.log`.
    *   `GPSIMULogger` lee datos del puerto serie -> Guarda en `data/imu_gps_logs/YYYY/MM/YYYYMMDD_...csv`.

2.  **Procesamiento (Bajo demanda desde la GUI):**
    *   `log_processor` lee `.log` de `can_logs/`.
    *   Usa el `.dbc` de `assets/dbc/`.
    *   Escribe los resultados en `data/csv_exports/canlog_YYYYMMDD.csv`.

3.  **Acceso:**
    *   El usuario interactúa con la `GUI` para controlar los procesos.
    *   `WebServer` sirve los archivos de `csv_exports/` para ser accedidos desde un navegador web.

## 5. Guía de Puesta en Marcha

Sigue estos pasos para replicar el sistema desde cero en una Raspberry Pi con Raspberry Pi OS.

### 5.1. Prerrequisitos de Hardware

*   Raspberry Pi 3B+ o superior.
*   Tarjeta SD de al menos 16GB.
*   Interfaz CAN HAT (ej. MCP2515) correctamente conectada a los pines GPIO.
*   Módulo GPS/IMU conectado al puerto serie (`/dev/tty...`).
*   Fuente de alimentación adecuada.
*   (Opcional) Botones físicos conectados a los pines GPIO definidos en `config.py`.

### 5.2. Prerrequisitos de Software

1.  **Actualizar el Sistema:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

2.  **Instalar Dependencias del Sistema:** `can-utils` es esencial para la comunicación CAN.
    ```bash
    sudo apt install -y python3-pip python3-tk can-utils
    ```

3.  **Instalar Librerías de Python:**
    ```bash
    pip3 install cantools RPi.GPIO pyserial
    ```

### 5.3. Configuración del Sistema (Interfaz CAN)

1.  **Habilitar la interfaz SPI** (necesaria para la mayoría de los CAN HATs).
    `sudo raspi-config` -> `Interface Options` -> `SPI` -> `Enable`.

2.  **Configurar el Overlay del CAN HAT.** Edita el fichero `/boot/config.txt`:
    `sudo nano /boot/config.txt`
    Añade estas líneas al final (ajusta `oscillator` y `interrupt` según las especificaciones de tu HAT):
    ```
    dtparam=spi=on
    dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
    ```

3.  Reinicia la Raspberry Pi: `sudo reboot`.

4.  **Verifica que la interfaz CAN aparece.** Después de reiniciar, ejecuta:
    `ip link show can0`
    Si el comando muestra la interfaz `can0`, la configuración es correcta.

### 5.4. Instalación de la Aplicación

1.  **Clona o copia la carpeta del proyecto** a la ubicación deseada, por ejemplo, `/home/cosigein/hums_project`.

2.  **Revisa `config.py`** y ajusta cualquier parámetro si es necesario (pines GPIO, puertos, etc.).

3.  **Coloca el archivo `hums_app.service` en su lugar.**
    ```bash
    sudo cp /home/cosigein/hums_project/hums_app.service /etc/systemd/system/hums_app.service
    ```

4.  **Recarga el demonio de systemd** para que reconozca el nuevo servicio.
    ```bash
    sudo systemctl daemon-reload
    ```

5.  **Habilita el servicio** para que se inicie automáticamente en cada arranque.
    ```bash
    sudo systemctl enable hums_app.service
    ```

### 5.5. Primer Arranque y Verificación

1.  **Inicia el servicio manualmente** para una primera prueba (o simplemente reinicia la Pi).
    ```bash
    sudo systemctl start hums_app.service
    ```
2.  **Verifica el estado del servicio.**
    ```bash
    systemctl status hums_app.service
    ```
    Deberías ver un estado "active (running)".
3.  **Revisa los logs del servicio.**
    ```bash
    journalctl -u hums_app.service -f
    ```
    Aquí verás los mensajes de `logging` de la aplicación, lo que es invaluable para la depuración. Presiona `Ctrl+C` para salir.

4.  Si tienes un entorno de escritorio, la **interfaz gráfica debería aparecer automáticamente**.

## 6. Uso y Operación

*   **Modo Autónomo:** Una vez configurado el servicio, el sistema es completamente autónomo. La GUI se lanzará al arrancar. Puedes cerrar la GUI, y los procesos de logging (si los iniciaste desde ella) seguirán corriendo porque son hilos independientes. Para detener todo, detén el servicio con `sudo systemctl stop hums_app.service`.

*   **Interacción con la GUI:** La interfaz es el principal punto de control. Desde ella puedes:
    *   Iniciar y detener el registro de datos OBD y GPS/IMU.
    *   Iniciar y detener el servidor web.
    *   Ejecutar el procesamiento de logs para generar los archivos CSV.

*   **Acceso Web:** Con el servidor web iniciado, abre un navegador en otro dispositivo de la misma red y ve a `http://<IP_DE_LA_RASPBERRY>:9000`. Podrás ver, descargar y gestionar los archivos CSV procesados.

## 7. Mantenimiento y Troubleshooting

*   **"La interfaz CAN no funciona"**:
    *   Verifica la salida de `dmesg | grep mcp251x` para ver si el driver se cargó correctamente.
    *   Asegúrate de que las líneas en `/boot/config.txt` son correctas para tu HAT.

*   **"La GUI no aparece al arrancar"**:
    *   Verifica `systemctl status hums_app.service` y `journalctl -u hums_app.service`. El error probablemente estará ahí.
    *   Asegúrate de que las líneas `Environment=DISPLAY=:0` y `Environment=XAUTHORITY=...` están en el archivo del servicio y que la ruta a `.Xauthority` es correcta para tu usuario.

*   **"No se registran datos"**:
    *   Comprueba los logs del servicio. Puede ser un error de permisos en las carpetas de `data/`. Asegúrate de que el usuario `cosigein` es propietario: `sudo chown -R cosigein:cosigein /home/cosigein/hums_project` y `sudo chown -R cosigein:cosigein /home/cosigein/hums_data`.

*   **Gestión del Espacio en Disco:** Los archivos de log pueden crecer. Considera implementar un script `cron` que elimine logs de más de 30 días para evitar que la tarjeta SD se llene.