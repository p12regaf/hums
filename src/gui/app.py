# ./src/gui/app.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog, font
import threading
import subprocess
import os
import time
from datetime import datetime
import logging
import shutil
import glob
import select

# --- Importación de Configuración Centralizada ---
# Todas las rutas, credenciales y configuraciones se importan desde aquí.
import config

# --- Carga Condicional de Módulos ---
# Usamos la variable IS_RASPBERRY_PI del archivo de configuración.
if config.IS_RASPBERRY_PI:
    import serial
    # En un futuro, estas clases contendrían la lógica de hardware
    # from src.core.obd_logger import OBDLogger 
    # from src.core.gps_imu_logger import GPSIMULogger
    # from src.services.gpio_monitor import GPIOMonitor
else:
    logging.warning("No se detectó una Raspberry Pi. Se usarán algunas funciones simuladas.")

# Por ahora, muchas de las funciones de hardware se implementarán directamente 
# en la clase de la GUI como en el Código 1, para replicar su comportamiento exacto.
from src.services.web_server import WebServer # Mantenemos el servidor modular

class Application(tk.Tk):
    """
    Clase principal de la interfaz gráfica HUMS.
    Versión Refactorizada: La configuración está externalizada en config.py
    """
    # --- Estilos (del Código 2) ---
    BG_COLOR = "#1e293b"
    FRAME_BG_COLOR = "#334155"
    SIDEBAR_BG_COLOR = "#475569"
    TEXT_COLOR = "#ffffff"
    BUTTON_BG_COLOR = "#64748b"
    SUCCESS_COLOR = "#22c55e"
    ERROR_COLOR = "#ef4444"
    INFO_COLOR = "#3b82f6"
    FONT_TITLE = ("Noto Sans", 22, "bold")
    FONT_HEADER = ("Noto Sans", 16, "bold")
    FONT_NORMAL = ("Noto Sans", 10)
    FONT_BUTTON = ("Noto Sans", 12)
    
    def __init__(self):
        super().__init__()
        # Aseguramos que los directorios necesarios existan al iniciar
        config.setup_directories()

        self.title("HUMS Interface")
        self.version = config.APP_VERSION # Versión desde config
        self.attributes('-fullscreen', True)
        self.configure(bg=self.BG_COLOR)
        self.bind("<Escape>", self.toggle_fullscreen)

        # --- Lógica de Backend (del Código 2) ---
        self.web_server = WebServer(directory=config.CSV_DIR, port=config.WEB_SERVER_PORT)
        # self.obd_logger = OBDLogger() # Se manejará directamente por ahora
        # self.gps_logger = GPSIMULogger() # Se manejará directamente por ahora

        # --- Estado y UI (Mezcla de Código 1 y 2) ---
        self.current_screen_frame = None
        self.is_fullscreen = True
        self.logged_in = False # Flag para el sistema de login

        # Variables de estado del Código 1
        self.can_active = tk.BooleanVar(value=False)

        # Variables para internacionalización (del Código 1)
        self.language_var = tk.StringVar(value="Español")
        self.translations = {
            "Español": {
                "title": "HUMS Interface", "vehicle_info": "⚙️ Información del Vehículo", "can_traffic": "Registro CAN",
                "requests": "Solicitudes", "communications": "Comunicaciones", "hums_config": "⚡ Configuración HUMS",
                "open_server": "Abrir Servidor", "csv": "Archivos CSV", "logs_data": "Ver Archivos de Logs",
                "logs_config": "⚙️ Ver Logs Configuración", "back": "⬅ Volver a Inicio", "read_vin": "Leer VIN",
                "read_cvn": "Leer CVN", "read_dtcs": "Leer DTCs", "vin_section": "VIN del Vehículo",
                "cvn_section": "CVN del Vehículo", "dtc_section": "Códigos de Falla (DTCs)",
                "vin_not_read": "VIN no leído", "cvn_not_read": "CVN no leído",
                "config_date": "Configurar fecha y hora (yyyy-mm-dd HH:MM):", "update_date": "Actualizar Fecha y Hora",
                "chassis_number": "Número de bastidor:", "add_chassis": "Agregar Número de Bastidor",
                "verify_services": "Verificar Servicios", "name": "Nombre:", "add_name": "Agregar Nombre",
                "finish": "Finalizar", "service_status": "Estado de los servicios",
                "verification_success": "Verificación terminada con éxito.", "server_title": "Servidor de Archivos",
                "server_info": "Información del Servidor", "server_path": "Ruta", "server_status_label": "Estado:",
                "server_running": "EJECUTANDO", "server_stopped": "DETENIDO", "start_server": "Iniciar Servidor",
                "stop_server": "Detener Servidor", "wifi": "📶 WiFi", "imu_gps": "📍 IMU/GPS",
                "file_viewer_title": "Visor de Archivos", "file_name": "Nombre del Archivo", "file_size": "Tamaño",
                "file_date": "Fecha Modificación", "open_file": "Abrir", "delete_file": "Eliminar",
                "refresh_list": "Actualizar Lista", "copy_to_usb": "Copiar a USB", "no_files": "No se encontraron archivos",
                "confirm_delete": "¿Está seguro de que desea eliminar este archivo?", "file_deleted": "Archivo eliminado",
                "delete_error": "Error al eliminar el archivo", "copy_success": "Archivos copiados a {}",
                "copy_error": "Error al copiar", "no_usb": "No se encontró USB", "login_title": "Acceso Restringido",
                "login_user": "Usuario:", "login_pass": "Contraseña:", "login_accept": "Aceptar",
                "login_cancel": "Cancelar", "login_error": "Usuario o contraseña incorrectos",
                "imu_gps_status": "Estado IMU/GPS:", "imu_gps_active": "ACTIVO", "imu_gps_inactive": "INACTIVO",
                "reset_sensors": "Reiniciar Sensores", "activate_gps": "Activar GPS", "deactivate_gps": "Desactivar GPS",
                "view_data": "Ver Datos", "reset_success": "Sensores reiniciados", "reset_error": "Error al reiniciar",
                "gps_activated": "GPS activado", "gps_deactivated": "GPS desactivado", "gps_error": "Error al cambiar estado del GPS",
                "warning_gps": "⚠️ ANTES DE ACTIVAR EL GPS, ASEGURARSE DE QUE ESTÁ CONECTADO",
                "wifi_edit_dhcp": "Editar dhcpcd.conf"
            },
            "Inglés": {}, "Alemán": {} # Omitido por brevedad
        }

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.language_var.trace_add("write", self.on_language_change)
        logging.info("GUI de la aplicación HUMS (Refactorizada) inicializada.")

    def setup_ui(self):
        # Header
        self.header = tk.Frame(self, bg=self.FRAME_BG_COLOR, height=60)
        self.header.pack(fill=tk.X, side=tk.TOP, padx=10, pady=10)
        self.header.pack_propagate(False)
        self.title_label = tk.Label(self.header, text="", font=self.FONT_TITLE, bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR)
        self.title_label.pack(side=tk.LEFT, padx=20)
        
        language_dropdown = ttk.Combobox(self.header, textvariable=self.language_var, values=list(self.translations.keys()), state="readonly")
        language_dropdown.pack(side=tk.RIGHT, padx=20)

        # Sidebar
        self.sidebar = tk.Frame(self, bg=self.SIDEBAR_BG_COLOR, width=250)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=(0, 10))
        self.sidebar.pack_propagate(False)
        
        # Mapa de rutas obtenido desde config.py
        path_map = {
            "csv": config.CSV_DIR,
            "logs_config": config.CONFIG_LOGS_DIR,
            "logs_data": config.APP_LOGS_DIR
        }

        self.sidebar_buttons = {}
        for key, path in path_map.items():
            btn = tk.Button(self.sidebar, text="", font=self.FONT_BUTTON, bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=lambda k=key, p=path: self._create_file_viewer_screen(k, p), anchor="w")
            btn.pack(pady=10, padx=10, fill=tk.X, ipady=5)
            self.sidebar_buttons[key] = btn

        # Main Frame
        self.main_frame = tk.Frame(self, bg=self.BG_COLOR)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.show_main_screen()
        self.on_language_change()

    def show_main_screen(self):
        # ... (código sin cambios, se omite por brevedad)
        self._clear_main_frame()
        self.active_screen_key = "main" # Para el refresco de idioma
        
        button_frame = tk.Frame(self.current_screen_frame, bg=self.BG_COLOR)
        button_frame.pack(fill=tk.BOTH, expand=True, padx=50, pady=20)
        
        self.main_buttons_map = {
            "vehicle_info": self.show_vehicle_info,
            "can_traffic": self.show_can_traffic,
            "requests": lambda: self.show_login_screen("requests", self.show_requests),
            "communications": self.show_communications,
            "hums_config": self.show_hums_config,
            "open_server": self.show_open_server,
            "wifi": lambda: self.show_login_screen("wifi", self.show_wifi),
            "imu_gps": self.show_imu_gps
        }

        self.main_button_widgets = {}
        lang = self.language_var.get()
        for key, command in self.main_buttons_map.items():
            text = self.translations[lang].get(key, key)
            btn = tk.Button(button_frame, text=text, font=("Noto Sans", 14, "bold"), bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=command)
            btn.pack(fill=tk.X, pady=8, ipady=10)
            self.main_button_widgets[key] = btn

        # Footer con ID y Versión
        footer_frame = tk.Frame(self.current_screen_frame, bg=self.BG_COLOR)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        try:
            # Usamos la ruta desde config.py
            with open(config.DEVICE_ID_FILE, "r") as f:
                device_id = f.read().strip()
        except Exception:
            device_id = "No disponible"
        
        tk.Label(footer_frame, text=f"Nº ID: {device_id}", font=self.FONT_NORMAL, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)
        tk.Label(footer_frame, text=f"Versión {self.version}", font=self.FONT_NORMAL, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.RIGHT)

    # --- Resto de las pantallas ... ---
    # (Se omiten por brevedad las funciones _clear_main_frame, _create_screen_header, etc. que no cambian)
    def _clear_main_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.current_screen_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        self.current_screen_frame.pack(fill=tk.BOTH, expand=True)

    def _create_screen_header(self, title_key):
        header_frame = tk.Frame(self.current_screen_frame, bg=self.BG_COLOR)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        lang = self.language_var.get()
        title_text = self.translations[lang].get(title_key, title_key.replace("_", " ").title())
        tk.Label(header_frame, text=f"<>  {title_text}", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack()
        return self.current_screen_frame

    def _create_back_button(self):
        lang = self.language_var.get()
        back_text = self.translations[lang]["back"]
        tk.Button(self.current_screen_frame, text=back_text, font=self.FONT_BUTTON, bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=self.show_main_screen).pack(pady=20)


    def show_open_server(self):
        self._clear_main_frame()
        self.active_screen_key = "open_server"
        container = self._create_screen_header("server_title")
        lang = self.language_var.get()
        
        info_frame = tk.LabelFrame(container, text=self.translations[lang]["server_info"], bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        info_frame.pack(fill=tk.X, padx=20, pady=20)
        ip_addr = subprocess.getoutput("hostname -I").split()[0] if config.IS_RASPBERRY_PI else "127.0.0.1"
        # Usamos valores de config.py
        info_text = f"IP: {ip_addr}    Puerto: {config.WEB_SERVER_PORT}\n{self.translations[lang]['server_path']}: {config.CSV_DIR}"
        tk.Label(info_frame, text=info_text, justify=tk.LEFT, bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).pack(anchor="w")
        
        status_frame = tk.Frame(container, bg=self.BG_COLOR)
        status_frame.pack(pady=10)
        tk.Label(status_frame, text=self.translations[lang]["server_status_label"], bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON).pack(side=tk.LEFT)
        self.server_status_label = tk.Label(status_frame, text="", bg=self.BG_COLOR, font=(self.FONT_BUTTON[0], self.FONT_BUTTON[1], 'bold'))
        self.server_status_label.pack(side=tk.LEFT, padx=10)
        
        button_frame = tk.Frame(container, bg=self.BG_COLOR)
        button_frame.pack(pady=10)
        self.server_toggle_button = tk.Button(button_frame, text="", relief="flat", command=self.toggle_web_server, font=self.FONT_BUTTON)
        self.server_toggle_button.pack()
        
        self.update_server_ui()
        self._create_back_button()

    def show_imu_gps(self):
        self._clear_main_frame()
        self.active_screen_key = "imu_gps"
        container = self._create_screen_header("imu_gps")
        lang = self.language_var.get()

        # ... (resto de la UI de IMU/GPS)
        status_frame = tk.Frame(container, bg=self.BG_COLOR)
        status_frame.pack(fill="x", pady=20, padx=20)
        tk.Label(status_frame, text=self.translations[lang]["imu_gps_status"], bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON).pack(side=tk.LEFT)
        self.gps_status_label = tk.Label(status_frame, text="", bg=self.BG_COLOR, font=(self.FONT_BUTTON[0], self.FONT_BUTTON[1], 'bold'))
        self.gps_status_label.pack(side=tk.LEFT, padx=10)

        button_frame = tk.Frame(container, bg=self.BG_COLOR)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text=self.translations[lang]["reset_sensors"], bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=self.reset_imu_sensors).pack(side=tk.LEFT, padx=10)
        self.gps_toggle_button = tk.Button(button_frame, text="", relief="flat", command=self.toggle_gps, font=self.FONT_BUTTON)
        self.gps_toggle_button.pack(side=tk.LEFT, padx=10)
        # Usamos la ruta de IMU/GPS desde config.py
        tk.Button(button_frame, text=self.translations[lang]["view_data"], bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=lambda: self._create_file_viewer_screen("imu_gps_data", config.IMU_GPS_DATA_DIR)).pack(side=tk.LEFT, padx=10)
        
        warning_frame = tk.LabelFrame(container, bg=self.FRAME_BG_COLOR, bd=1, relief="solid")
        warning_frame.pack(fill=tk.X, pady=20, padx=20, ipady=5)
        tk.Label(warning_frame, text=self.translations[lang]["warning_gps"], bg=self.FRAME_BG_COLOR, fg="#fbbf24", font=("Noto Sans", 10, "bold")).pack()
        
        self.update_gps_ui()
        self._create_back_button()

    def show_wifi(self):
        self._clear_main_frame()
        self.active_screen_key = "wifi"
        container = self._create_screen_header("wifi")
        lang = self.language_var.get()
        tk.Button(container, text=self.translations[lang]["wifi_edit_dhcp"], command=self.edit_dhcpcd_conf, font=self.FONT_BUTTON, bg=self.INFO_COLOR, fg=self.TEXT_COLOR).pack(pady=20)
        self._create_back_button()

    def on_language_change(self, *args):
        lang = self.language_var.get()
        self.title_label.config(text=self.translations[lang]["title"])
        # Corregido: Iterar sobre los widgets de botón, no sobre el diccionario de comandos
        for key, btn in self.sidebar_buttons.items():
            btn.config(text=self.translations[lang].get(key, key))
        if hasattr(self, 'main_button_widgets'):
             for key, btn in self.main_button_widgets.items():
                btn.config(text=self.translations[lang].get(key, key))
        if hasattr(self, 'active_screen_key') and self.active_screen_key != "main":
            screen_func_map = {
                "vehicle_info": self.show_vehicle_info,
                "hums_config": self.show_hums_config,
                "open_server": self.show_open_server,
                "imu_gps": self.show_imu_gps,
                # ...
            }
            if self.active_screen_key in screen_func_map:
                screen_func_map[self.active_screen_key]()
    
    def guardar_en_log(self, mensaje):
        # Usamos la ruta del log de calidad desde config.py
        log_file = config.QUALITY_LOG_FILE
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "a") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {mensaje}\n")
        except Exception as e:
            print(f"Error al guardar en log: {e}")

    def verificar_servicios(self):
        # La lista de servicios ahora viene de config.py
        servicios = config.SYSTEMD_SERVICES
        resultados = ""
        for s in servicios:
            try:
                estado = subprocess.check_output(["systemctl", "is-active", s]).decode().strip()
            except subprocess.CalledProcessError:
                estado = "inactivo"
            resultados += f"{s}: {estado.upper()}\n"
        self.service_text.config(state=tk.NORMAL)
        self.service_text.delete(1.0, tk.END)
        self.service_text.insert(tk.END, resultados)
        self.service_text.config(state=tk.DISABLED)
        self.guardar_en_log("Verificación de servicios realizada.")

    def toggle_can(self):
        def _toggle_can_thread():
            self.activate_can_btn.config(state="disabled")
            can_if = config.CAN_INTERFACE
            can_br = str(config.CAN_BITRATE)
            if not self.can_active.get():
                try:
                    subprocess.run(["sudo", "ip", "link", "set", can_if, "down"], check=True)
                    subprocess.run(["sudo", "ip", "link", "set", can_if, "type", "can", "bitrate", can_br], check=True)
                    subprocess.run(["sudo", "ip", "link", "set", can_if, "up"], check=True)
                    self.can_active.set(True)
                    self.after(0, self.update_can_ui)
                except Exception as e:
                    self.after(0, messagebox.showerror, "Error", f"Fallo al activar CAN: {e}")
                    self.can_active.set(False)
                    self.after(0, self.update_can_ui)
            else:
                try:
                    subprocess.run(["sudo", "ip", "link", "set", can_if, "down"], check=True)
                    self.can_active.set(False)
                    self.after(0, self.update_can_ui)
                except Exception as e:
                    self.after(0, messagebox.showerror, "Error", f"Fallo al desactivar CAN: {e}")
            self.after(0, lambda: self.activate_can_btn.config(state="normal"))

        threading.Thread(target=_toggle_can_thread, daemon=True).start()

    def request_and_log_can(self, request_cmd, log_file, log_header, read_btn_widget):
        def _thread():
            can_if = config.CAN_INTERFACE
            try:
                with open(log_file, 'w') as f:
                    f.write(f"=== {log_header} ===\n")
                
                candump_proc = subprocess.Popen(["candump", f"{can_if},7DF:7FF,7E8:7FF"], stdout=subprocess.PIPE, text=True)
                subprocess.run(["cansend", can_if, request_cmd], check=True)
                
                start_time = time.time()
                first_frame_received = False
                while time.time() - start_time < 2.0:
                    ready = select.select([candump_proc.stdout], [], [], 0.1)
                    if ready[0]:
                        line = candump_proc.stdout.readline().strip()
                        with open(log_file, 'a') as f:
                            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S.%f} - {line}\n")
                        if "7E8" in line and "10" in line and not first_frame_received:
                             first_frame_received = True
                             subprocess.run(["cansend", can_if, "7E0#3000050000000000"], check=True)

                candump_proc.terminate()
                self.after(0, lambda: read_btn_widget.config(state="normal"))
                self.after(0, messagebox.showinfo, "Éxito", f"Solicitud para '{log_header}' completada. Puede leer el log.")
            except Exception as e:
                self.after(0, messagebox.showerror, "Error", f"Error en solicitud CAN: {e}")

        # Usamos la ruta del log de información desde config.py
        threading.Thread(target=_thread, daemon=True).start()

    def request_vin(self):
        self.request_vin_btn.config(state="disabled")
        self.request_and_log_can("7DF#0209020000000000", config.CAN_INFO_LOG_FILE, "Lectura VIN", self.read_vin_btn)

    def request_cvn(self):
        self.request_cvn_btn.config(state="disabled")
        self.request_and_log_can("7DF#0209060000000000", config.CAN_INFO_LOG_FILE, "Lectura CVN", self.read_cvn_btn)

    def read_vin_from_log(self):
        try:
            with open(config.CAN_INFO_LOG_FILE, 'r') as f:
                lines = f.readlines()
            # ... (la lógica de parseo no cambia)
            vin_data = []
            for line in lines:
                if "7E8" in line:
                    parts = line.split()
                    data_bytes_str = parts[parts.index("[8]") + 1:]
                    hex_bytes = [int(b, 16) for b in data_bytes_str]
                    if hex_bytes[0] & 0xF0 == 0x10: # First Frame
                        vin_data.extend(hex_bytes[5:])
                    elif hex_bytes[0] & 0xF0 == 0x20: # Consecutive Frame
                        vin_data.extend(hex_bytes[1:])

            if vin_data:
                vin = bytes(vin_data).decode('ascii').strip('\x00')
                self.display_info(self.vin_text, f"VIN: {vin}")
            else:
                self.display_info(self.vin_text, "No se encontraron datos de VIN en el log.")
        except Exception as e:
            self.display_info(self.vin_text, f"Error leyendo log: {e}")

    def reset_imu_sensors(self):
        lang = self.language_var.get()
        if not config.IS_RASPBERRY_PI:
            messagebox.showinfo("Simulación", "Sensores IMU reseteados (simulado).")
            return
        try:
            port = config.GPS_IMU_SERIAL_PORT
            if not port:
                ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
                if not ports: raise Exception("No se encontró puerto serie.")
                port = ports[0]

            with serial.Serial(port, config.GPS_IMU_BAUD_RATE, timeout=1) as ser:
                ser.write(b'110\n')
                if ser.readline().decode().strip() == '210':
                    messagebox.showinfo("Éxito", self.translations[lang]["reset_success"])
                else:
                    raise Exception("Respuesta inesperada del sensor.")
        except Exception as e:
            messagebox.showerror("Error", f"{self.translations[lang]['reset_error']}: {e}")
            
    def edit_dhcpcd_conf(self):
        if not config.IS_RASPBERRY_PI:
            messagebox.showinfo("Simulación", f"Abriendo {config.WIFI_CONFIG_FILE} (simulado).")
            return
        try:
            subprocess.run(['sudo', config.DEFAULT_TEXT_EDITOR, config.WIFI_CONFIG_FILE])
        except FileNotFoundError:
             messagebox.showerror("Error", f"Editor '{config.DEFAULT_TEXT_EDITOR}' no encontrado. Instálelo para usar esta función.")

    def _open_selected_file(self, tree, directory):
        selected_item = tree.selection()
        if not selected_item: return
        filename = tree.item(selected_item[0])["values"][0]
        if filename == self.translations[self.language_var.get()]["no_files"]: return
        filepath = os.path.join(directory, filename)
        try:
            subprocess.run([config.DEFAULT_TEXT_EDITOR, filepath])
        except FileNotFoundError:
             messagebox.showerror("Error", f"Editor '{config.DEFAULT_TEXT_EDITOR}' no encontrado.")
    
    def copy_to_usb(self, source_directory):
        lang = self.language_var.get()
        # Ruta base para USBs desde config.py
        usb_base_path = os.path.join(config.USB_MOUNT_BASE, os.getlogin())
        
        # Fallback a la ruta base si la específica del usuario no existe
        if not os.path.exists(usb_base_path):
            usb_base_path = config.USB_MOUNT_BASE

        try:
            if not os.path.exists(usb_base_path):
                raise FileNotFoundError(f"Directorio base de USB {usb_base_path} no encontrado.")

            # Busca subdirectorios en la ruta base (las unidades montadas)
            usb_devices = [d for d in os.listdir(usb_base_path) if os.path.isdir(os.path.join(usb_base_path, d))]
            if not usb_devices:
                messagebox.showinfo("Info", self.translations[lang]["no_usb"])
                return
            
            usb_path = os.path.join(usb_base_path, usb_devices[0])
            dest_folder_name = os.path.basename(source_directory) or "Logs"
            dest_path = os.path.join(usb_path, "HUMS_DATA", dest_folder_name)
            
            shutil.copytree(source_directory, dest_path, dirs_exist_ok=True)
            messagebox.showinfo("Éxito", self.translations[lang]["copy_success"].format(dest_path))

        except Exception as e:
            messagebox.showerror("Error", f"{self.translations[lang]['copy_error']}: {e}")

    def show_login_screen(self, target_screen_key, target_function):
        # ... (la UI no cambia, pero la lógica de validación sí)
        lang = self.language_var.get()
        login_window = tk.Toplevel(self)
        login_window.title(self.translations[lang]["login_title"])
        login_window.configure(bg=self.BG_COLOR)
        login_window.grab_set()
        
        tk.Label(login_window, text=self.translations[lang]["login_user"], bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=(10,0))
        user_entry = tk.Entry(login_window)
        user_entry.pack(pady=5, padx=20)
        
        tk.Label(login_window, text=self.translations[lang]["login_pass"], bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=(10,0))
        pass_entry = tk.Entry(login_window, show="*")
        pass_entry.pack(pady=5, padx=20)
        
        def validate():
            # Usamos credenciales desde config.py
            if user_entry.get() == config.ADMIN_USER and pass_entry.get() == config.ADMIN_PASSWORD:
                self.logged_in = True
                login_window.destroy()
                target_function()
            else:
                messagebox.showerror("Error", self.translations[lang]["login_error"], parent=login_window)

        btn_frame = tk.Frame(login_window, bg=self.BG_COLOR)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=self.translations[lang]["login_accept"], command=validate, bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text=self.translations[lang]["login_cancel"], command=login_window.destroy, bg=self.ERROR_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT, padx=10)


    # --- Resto de funciones sin cambios (placeholders, cierre, etc.) ---
    # (Se omiten por brevedad: show_can_traffic, show_requests, etc.)
    def show_can_traffic(self):
        self._clear_main_frame()
        self.active_screen_key = "can_traffic"
        container = self._create_screen_header("can_traffic")
        tk.Label(container, text="Pantalla de Registro CAN en construcción...", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=50)
        self._create_back_button()

    def show_requests(self):
        self._clear_main_frame()
        self.active_screen_key = "requests"
        container = self._create_screen_header("requests")
        tk.Label(container, text="Pantalla de Solicitudes en construcción...", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=50)
        self._create_back_button()
        
    def show_communications(self):
        self._clear_main_frame()
        self.active_screen_key = "communications"
        container = self._create_screen_header("communications")
        tk.Label(container, text="Pantalla de Comunicaciones en construcción...", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=50)
        self._create_back_button()

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def on_closing(self):
        if messagebox.askokcancel("Salir", "¿Seguro que quieres salir?"):
            logging.info("Cerrando aplicación...")
            if self.web_server.is_running(): self.web_server.stop()
            self.destroy()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = Application()
    app.mainloop()