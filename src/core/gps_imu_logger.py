# ./src/core/gps_imu_logger.py
import serial
import csv
import os
import re
import time
import logging
import threading
from datetime import datetime

import config

class GPSIMULogger:
    """
    Gestiona la lectura de datos de un módulo IMU/GPS a través del puerto serie
    y los guarda en archivos CSV organizados por fecha.
    """
    def __init__(self):
        self.serial_port = config.GPS_IMU_SERIAL_PORT
        self.baud_rate = config.GPS_IMU_BAUD_RATE
        
        self._running = False
        self._thread = None
        self.serial_conn = None
        self.csv_file = None
        self.csv_writer = None
        self.current_log_date = None
        
        logging.info("GPS/IMU Logger inicializado.")

    def start(self):
        """Inicia el hilo de registro de GPS/IMU."""
        if self._running:
            logging.warning("El logger GPS/IMU ya está en ejecución.")
            return

        logging.info("Iniciando logger GPS/IMU...")
        self._running = True
        self._thread = threading.Thread(target=self._logging_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Detiene el hilo de registro de GPS/IMU."""
        if not self._running:
            logging.warning("El logger GPS/IMU no está en ejecución.")
            return

        logging.info("Deteniendo logger GPS/IMU...")
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        if self.csv_file:
            self.csv_file.close()
            
        logging.info("Logger GPS/IMU detenido.")

    def is_running(self):
        return self._running
        
    def _initialize_log_file(self):
        """Prepara el archivo CSV para el día actual, creando directorios si es necesario."""
        now = datetime.now()
        self.current_log_date = now.strftime('%Y%m%d')
        year_folder = now.strftime('%Y')
        month_folder = now.strftime('%m') # Solo el mes

        log_path = os.path.join(config.IMU_GPS_LOG_DIR, year_folder, month_folder)
        os.makedirs(log_path, exist_ok=True)
        
        file_path = os.path.join(log_path, f"{self.current_log_date}_IMU_GPS_DATA.csv")

        # Determinar número de sesión
        session_num = 1
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    sessions = re.findall(r'===== Sesión (\d+)', content, re.MULTILINE)
                    if sessions:
                        session_num = int(sessions[-1]) + 1
            except Exception as e:
                logging.error(f"No se pudo leer el archivo de log para determinar la sesión: {e}")

        self.csv_file = open(file_path, mode='a', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        session_header = f"===== Sesión {session_num} - {now.strftime('%Y-%m-%d %H:%M:%S')} ====="
        self.csv_writer.writerow([session_header])
        self.csv_writer.writerow([
            "timestamp", "accel_x_m_s2", "accel_y_m_s2", "accel_z_m_s2",
            "gyro_x_rad_s", "gyro_y_rad_s", "gyro_z_rad_s", "latitude", "longitude"
        ])
        self.csv_file.flush()
        logging.info(f"Registrando datos de GPS/IMU en {file_path}, Sesión {session_num}")

    def _connect_serial(self):
        """Intenta establecer conexión con el puerto serie."""
        while self._running:
            try:
                if not os.path.exists(self.serial_port):
                    logging.warning(f"Esperando que el dispositivo {self.serial_port} se conecte...")
                    time.sleep(2)
                    continue

                self.serial_conn = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
                self.serial_conn.reset_input_buffer()
                logging.info(f"Conectado exitosamente a {self.serial_port}.")
                return True
            except serial.SerialException as e:
                logging.error(f"No se pudo abrir el puerto serie {self.serial_port}: {e}. Reintentando en 5 segundos...")
                time.sleep(5)
        return False

    def _logging_loop(self):
        """Bucle principal que lee del puerto serie y escribe en el archivo."""
        if not self._connect_serial():
            self._running = False
            return
            
        self._initialize_log_file()
        
        while self._running:
            try:
                # Comprobar si es un nuevo día para rotar el archivo de log
                if datetime.now().strftime('%Y%m%d') != self.current_log_date:
                    self.csv_file.close()
                    self._initialize_log_file()

                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line:
                        parts = line.split(',')
                        if len(parts) == 8: # 3 accel, 3 gyro, 2 gps
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            self.csv_writer.writerow([timestamp] + parts)
                            self.csv_file.flush()
                        else:
                            logging.warning(f"Trama malformada recibida: {line}")
                else:
                    time.sleep(0.05) # Pequeña pausa si no hay datos

            except serial.SerialException as e:
                logging.error(f"Error de puerto serie: {e}. Intentando reconectar...")
                if self.serial_conn: self.serial_conn.close()
                self._connect_serial()
            except Exception as e:
                logging.error(f"Error inesperado en el bucle de GPS/IMU: {e}")
                time.sleep(1)