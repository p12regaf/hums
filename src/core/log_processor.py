# ./src/core/log_processor.py
import os
import glob
import cantools
import csv
import logging
from datetime import datetime

import config

class OBDDataExtractor:
    """
    Una clase para extraer datos OBD especiales (VIN, CVN, DTCs) de tramas CAN,
    gestionando el estado interno para mensajes multi-trama como el VIN.
    """
    def __init__(self):
        self.vin_buffer = []
        self.vin_completed = False

    def reset_session(self):
        """Reinicia el estado para una nueva sesión de logging."""
        self.vin_buffer = []
        self.vin_completed = False

    def extract(self, can_id, data):
        """
        Intenta extraer datos especiales. Devuelve un diccionario si tiene éxito,
        o None si no es una trama de interés.
        """
        if can_id != 0x7E8 or len(data) < 3:
            return None

        # --- VIN (modo 09 PID 02) ---
        # Primera trama (First Frame)
        if data[0] == 0x10 and len(data) > 3 and data[3] == 0x02:
            self.vin_buffer = [data[3:]]
            self.vin_completed = False
            return None
        # Tramas consecutivas (Consecutive Frames)
        elif data[0] in (0x21, 0x22) and self.vin_buffer:
            self.vin_buffer.append(data[1:])
            if data[0] == 0x22: # Última trama
                flat_buffer = [b for segment in self.vin_buffer for b in segment]
                # Los primeros 3 bytes del buffer son 11 (longitud), 49 (modo resp), 02 (PID resp)
                # El VIN real empieza desde el 4º byte.
                vin_bytes = flat_buffer[3:] 
                vin = ''.join(chr(b) for b in vin_bytes if 32 <= b <= 126).strip()
                self.vin_completed = True
                self.vin_buffer = [] # Limpiar para la próxima vez
                return {'type': 'VIN', 'data': vin}
            return None
        
        # Otros datos, modo y pid están en diferentes posiciones
        mode, pid = data[1], data[2]
        
        # --- CVN (modo 09 PID 06) ---
        if mode == 0x49 and pid == 0x06 and len(data) >= 8:
            cvn_bytes = data[4:8]
            cvn = ''.join(f"{b:02X}" for b in cvn_bytes)
            return {'type': 'CVN', 'data': cvn}

        # --- DTCs (Modo 03 o 07) ---
        if mode in (0x43, 0x47) and len(data) >= 3:
            num_dtcs = data[2]
            if num_dtcs == 0:
                return {'type': 'DTC', 'mode': mode, 'data': 'Sin códigos de error'}
            
            dtcs = []
            dtc_bytes = data[3 : 3 + num_dtcs * 2]
            for i in range(0, len(dtc_bytes), 2):
                if i + 1 < len(dtc_bytes):
                    msb, lsb = dtc_bytes[i], dtc_bytes[i+1]
                    if msb == 0 and lsb == 0: continue
                    first_char = ['P', 'C', 'B', 'U'][(msb & 0xC0) >> 6]
                    code = f"{first_char}{(msb & 0x3F):02X}{lsb:02X}"
                    dtcs.append(code)
            
            return {'type': 'DTC', 'mode': mode, 'data': ', '.join(dtcs)}

        return None


def _get_processed_files():
    """Lee la lista de archivos ya procesados."""
    if os.path.exists(config.PROCESSED_FILES_LOG):
        with open(config.PROCESSED_FILES_LOG, 'r') as f:
            return set(f.read().splitlines())
    return set()

def _mark_file_as_processed(filename):
    """Añade un archivo a la lista de procesados."""
    with open(config.PROCESSED_FILES_LOG, 'a') as f:
        f.write(f"{os.path.basename(filename)}\n")

def _transform_log_line(line):
    """Transforma el formato de log de candump al formato (timestamp, id, data)."""
    try:
        parts = line.strip().split()
        if len(parts) < 4 or not parts[0].startswith('('):
            return None
        timestamp = parts[0].strip('()')
        can_id = parts[2]
        data = ''.join(parts[4:])
        return timestamp, can_id, data
    except (IndexError, ValueError):
        return None

def process_log_file(log_file_path, db, extractor):
    """Procesa un único archivo de log y lo convierte a CSV."""
    log_filename = os.path.basename(log_file_path)
    csv_filename = log_filename.replace('.log', '.csv')
    output_csv_path = os.path.join(config.CSV_EXPORTS_DIR, csv_filename)

    decoded_entries = []

    with open(log_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Detectar cabecera de sesión
            if " " in line and not line.startswith("("):
                extractor.reset_session()
                decoded_entries.append({'Message Name': 'SESIÓN:', 'Decoded Data': line})
                continue
            
            # Procesar línea de datos CAN
            transformed = _transform_log_line(line)
            if not transformed:
                continue
            
            timestamp, can_id_str, data_hex = transformed
            
            try:
                can_id_int = int(can_id_str, 16)
                data_bytes = bytes.fromhex(data_hex)
                
                # Intentar extraer datos especiales (VIN, CVN, DTC)
                special_data = extractor.extract(can_id_int, data_bytes)
                if special_data:
                    entry = {'Timestamp': timestamp, 'CAN ID': can_id_str}
                    if special_data['type'] == 'VIN':
                        entry.update({'Message Name': 'VIN', 'Decoded Data': special_data['data']})
                    elif special_data['type'] == 'CVN':
                        entry.update({'Message Name': 'CVN', 'Decoded Data': special_data['data']})
                    elif special_data['type'] == 'DTC':
                        dtc_type = "Almacenados" if special_data['mode'] == 0x43 else "Pendientes"
                        entry.update({'Message Name': f'DTC {dtc_type}', 'Decoded Data': special_data['data']})
                    decoded_entries.append(entry)
                    continue

                # Decodificar con DBC
                message = db.get_message_by_frame_id(can_id_int)
                decoded_data = message.decode(data_bytes)
                
                pretty_data = ", ".join([f"{key}: {value}" for key, value in decoded_data.items()])
                decoded_entries.append({
                    'Timestamp': timestamp,
                    'CAN ID': can_id_str,
                    'Message Name': message.name,
                    'Decoded Data': pretty_data
                })

            except (KeyError, cantools.database.errors.DecodeError):
                # ID no encontrado en DBC o error de decodificación
                decoded_entries.append({
                    'Timestamp': timestamp,
                    'CAN ID': can_id_str,
                    'Message Name': 'Desconocido',
                    'Decoded Data': data_hex.upper()
                })
            except ValueError:
                # Error de formato en ID o datos
                continue
    
    # Escribir el archivo CSV
    with open(output_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['Timestamp', 'CAN ID', 'Message Name', 'Decoded Data']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', delimiter='|')
        
        # Escribir un encabezado simple
        csvfile.write("Timestamp | CAN ID | Message Name | Decoded Data\n")
        
        for entry in decoded_entries:
            # Manejo especial para la línea de sesión
            if entry.get('Message Name') == 'SESIÓN:':
                csvfile.write(f" | | {entry['Message Name']} | {entry['Decoded Data']}\n")
            else:
                writer.writerow(entry)

    logging.info(f"Archivo CSV generado en: {output_csv_path}")


def process_pending_logs():
    """
    Busca archivos .log que no hayan sido procesados, los traduce usando el DBC
    y los convierte a formato CSV.
    """
    logging.info("Iniciando procesamiento de logs pendientes...")
    
    try:
        db = cantools.database.load_file(config.DBC_FILE)
        logging.info("Archivo DBC cargado correctamente.")
    except Exception as e:
        logging.critical(f"No se pudo cargar el archivo DBC en {config.DBC_FILE}: {e}")
        return

    processed_files = _get_processed_files()
    current_date_str = datetime.now().strftime("%Y%m%d")
    all_log_files = glob.glob(os.path.join(config.CAN_LOG_DIR, '*.log'))

    files_to_process = [
        f for f in all_log_files
        if os.path.basename(f) not in processed_files and current_date_str not in os.path.basename(f)
    ]
    
    if not files_to_process:
        logging.info("No hay archivos de log pendientes para procesar.")
        return

    logging.info(f"Se encontraron {len(files_to_process)} archivos para procesar.")
    extractor = OBDDataExtractor()

    for log_file in sorted(files_to_process):
        logging.info(f"Procesando: {os.path.basename(log_file)}")
        try:
            process_log_file(log_file, db, extractor)
            _mark_file_as_processed(log_file)
            logging.info(f"Completado: {os.path.basename(log_file)}")
        except Exception as e:
            logging.error(f"Fallo al procesar el archivo {log_file}: {e}", exc_info=True)

    logging.info("Procesamiento de logs finalizado.")