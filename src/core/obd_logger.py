# ./src/core/obd_logger.py
import time
import os
import subprocess
import csv
import threading
import logging
from datetime import datetime

import config # Importamos la configuración centralizada

class OBDLogger:
    """
    Gestiona el registro automático de datos del bus CAN (OBD-II).
    Se ejecuta en un hilo separado y puede ser controlado mediante start() y stop().
    """
    def __init__(self):
        self.device_id = self._load_device_id()
        self.requests = self._load_requests_csv(config.OBD_REQUESTS_CSV)
        
        self._running = False
        self._thread = None
        self._candump_process = None
        
        # Variables para controlar solicitudes únicas
        self.vin_requested = False
        self.cvn_requested = False
        self.dtc_requested = False
        
        logging.info("OBDLogger inicializado.")

    def _load_device_id(self):
        """Carga el ID del dispositivo desde el archivo de texto."""
        try:
            with open(config.DEVICE_ID_FILE, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            logging.warning(f"Archivo de ID no encontrado en {config.DEVICE_ID_FILE}. Usando 'UNKNOWN_ID'.")
            return "UNKNOWN_ID"

    def _load_requests_csv(self, file_path):
        """Carga las solicitudes desde el archivo CSV de configuración."""
        requests = []
        try:
            with open(file_path, mode='r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    requests.append({
                        "ID": row["ID"],
                        "Datos": row["Datos"],
                        "Frecuencia": int(row["Frecuencia"]),
                        "Disparo": int(row["Disparo"]),
                        "Disparo_Unico": bool(int(row["Disparo Único"]))
                    })
            logging.info(f"{len(requests)} solicitudes OBD cargadas desde {file_path}")
        except FileNotFoundError:
            logging.error(f"El archivo de solicitudes CSV no se encontró en: {file_path}")
        except KeyError as e:
            logging.error(f"El archivo CSV debe contener la columna '{e}'. Revise los encabezados.")
        return requests

    def start(self):
        """Inicia el hilo de registro de OBD."""
        if self._running:
            logging.warning("El logger OBD ya está en ejecución.")
            return
        
        logging.info("Iniciando logger OBD...")
        self._running = True
        self._thread = threading.Thread(target=self._logging_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Detiene el hilo de registro de OBD."""
        if not self._running:
            logging.warning("El logger OBD no está en ejecución.")
            return

        logging.info("Deteniendo logger OBD...")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5) # Espera a que el hilo termine
            if self._thread.is_alive():
                logging.error("El hilo del logger OBD no se detuvo correctamente.")
        logging.info("Logger OBD detenido.")
        
    def is_running(self):
        return self._running

    def _initialize_can(self):
        """Inicializa la interfaz CAN del sistema."""
        try:
            subprocess.run(["sudo", "ip", "link", "set", config.CAN_INTERFACE, "down"], check=True)
            subprocess.run(["sudo", "ip", "link", "set", config.CAN_INTERFACE, "type", "can", "bitrate", str(config.CAN_BITRATE)], check=True)
            subprocess.run(["sudo", "ip", "link", "set", config.CAN_INTERFACE, "up"], check=True)
            logging.info(f"Interfaz {config.CAN_INTERFACE} inicializada a {config.CAN_BITRATE} bps.")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Fallo al inicializar la interfaz CAN: {e}")
            return False
        except FileNotFoundError:
            logging.error("Comando 'ip' no encontrado. Asegúrese de que can-utils está instalado y en el PATH.")
            return False

    def _send_can_request(self, msg_id, data):
        """Envía una única trama CAN."""
        command = f"cansend {config.CAN_INTERFACE} {msg_id}#{data}"
        try:
            # Usar shell=True es un riesgo de seguridad, pero el comando original lo usaba.
            # Una alternativa más segura sería dividir el comando en una lista de argumentos.
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error al enviar trama CAN '{command}': {e.stderr.strip()}")

    def _logging_loop(self):
        """El bucle principal que se ejecuta en el hilo."""
        if not self._initialize_can():
            self._running = False
            return

        log_file_path = os.path.join(config.CAN_LOG_DIR, f"canlog_{datetime.now().strftime('%Y%m%d')}.log")
        
        try:
            with open(log_file_path, "a") as log_file:
                # Escribir encabezado de sesión
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file.write(f"{timestamp} {self.device_id}\n")
                log_file.flush()
                
                logging.info(f"Registrando tráfico CAN en {log_file_path}")
                
                # Iniciar candump para capturar todo el tráfico
                self._candump_process = subprocess.Popen(
                    ["candump", config.CAN_INTERFACE],
                    stdout=log_file, # Redirige la salida estándar directamente al archivo de log
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                start_time = time.time()
                next_execution_times = {
                    f"{req['ID']}_{req['Datos']}": start_time + (req["Disparo"] / 1000.0)
                    for req in self.requests
                }
                
                while self._running:
                    current_time = time.time()
                    elapsed_time = current_time - start_time

                    # --- Enviar solicitudes especiales cronometradas ---
                    if elapsed_time >= 30 and not self.vin_requested:
                        self._send_can_request("7DF", "0209020000000000") # VIN
                        time.sleep(0.05)
                        self._send_can_request("7E0", "3000050000000000") # Flow Control
                        self.vin_requested = True

                    if elapsed_time >= 35 and not self.cvn_requested:
                        self._send_can_request("7DF", "0209060000000000") # CVN
                        self.cvn_requested = True
                        
                    if elapsed_time >= 40 and not self.dtc_requested:
                        self._send_can_request("7DF", "0103") # DTC Almacenados
                        time.sleep(1)
                        self._send_can_request("7DF", "0107") # DTC Pendientes
                        self.dtc_requested = True

                    # --- Procesar solicitudes del CSV ---
                    for req in self.requests:
                        req_id = f"{req['ID']}_{req['Datos']}"
                        if current_time >= next_execution_times.get(req_id, float('inf')):
                            self._send_can_request(req["ID"], req["Datos"])
                            
                            if not req["Disparo_Unico"]:
                                next_execution_times[req_id] = current_time + (req["Frecuencia"] / 1000.0)
                            else:
                                next_execution_times[req_id] = float('inf') # Ejecutar solo una vez
                    
                    time.sleep(0.01) # Pequeña pausa para no saturar la CPU
        
        except Exception as e:
            logging.error(f"Error en el bucle de registro OBD: {e}")
        
        finally:
            # Limpieza al salir del bucle
            if self._candump_process:
                self._candump_process.terminate()
                try:
                    self._candump_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._candump_process.kill()
                logging.info("Proceso candump detenido.")

            try:
                subprocess.run(["sudo", "ip", "link", "set", config.CAN_INTERFACE, "down"], check=True)
                logging.info(f"Interfaz {config.CAN_INTERFACE} desactivada.")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                 logging.error(f"Error al desactivar la interfaz CAN: {e}")