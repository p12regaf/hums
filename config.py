# ./config.py
import os

# --- Rutas del Proyecto ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.expanduser("~") # Ruta al home del usuario actual

# --- Rutas de Datos ---
DATA_DIR = os.path.join(HOME_DIR, "hums_data") # Carpeta principal de datos
CAN_LOG_DIR = os.path.join(DATA_DIR, "can_logs")
CSV_EXPORTS_DIR = os.path.join(DATA_DIR, "csv_exports")
IMU_GPS_LOG_DIR = os.path.join(DATA_DIR, "imu_gps_logs")
SYSTEM_LOG_DIR = os.path.join(DATA_DIR, "system_logs")
PROCESSED_FILES_LOG = os.path.join(DATA_DIR, "processed_files.txt")
DEVICE_ID_FILE = os.path.join(SYSTEM_LOG_DIR, "id.txt")

# --- Rutas de Assets ---
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DBC_FILE = os.path.join(ASSETS_DIR, "dbc", "CSS-Electronics-11-bit-OBD2-v2.1.dbc")
OBD_REQUESTS_CSV = os.path.join(ASSETS_DIR, "config_files", "solicitudes.csv")

# --- Configuración GPIO ---
# Se usa numeración BOARD
SHUTDOWN_PIN_1 = 37 # Pin para el script 'alarma.py'
SHUTDOWN_PIN_2 = 36 # Pin para el script 'apagar.py'
OBD_LOGGER_CONTROL_PIN = 16 # Pin para controlar el logger OBD

# --- Configuración de Red y Servicios ---
CAN_INTERFACE = "can0"
CAN_BITRATE = 500000
WEB_SERVER_PORT = 9000
GPS_IMU_SERIAL_PORT = '/dev/esp32_data'
GPS_IMU_BAUD_RATE = 115200

# --- Creación de directorios si no existen ---
def setup_directories():
    """Asegura que todos los directorios de datos existan."""
    print("Verificando estructura de directorios...")
    for path in [DATA_DIR, CAN_LOG_DIR, CSV_EXPORTS_DIR, IMU_GPS_LOG_DIR, SYSTEM_LOG_DIR]:
        os.makedirs(path, exist_ok=True)
    print("Estructura de directorios lista.")