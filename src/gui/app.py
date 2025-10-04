# ./src/gui/app.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import threading
import subprocess
import os
import time
from datetime import datetime
import logging
import shutil

# Importamos la configuración y los módulos de lógica
import config

# --- Carga Condicional de Módulos ---
if config.IS_RASPBERRY_PI:
    from src.core.obd_logger import OBDLogger
    from src.core.gps_imu_logger import GPSIMULogger
    from src.services.gpio_monitor import GPIOMonitor
else:
    # Si no estamos en una RPi, importamos las clases simuladas
    logging.warning("No se detectó una Raspberry Pi. Cargando módulos de hardware simulados (mocks).")
    from src.mocks.hardware_mocks import MockOBDLogger as OBDLogger
    from src.mocks.hardware_mocks import MockGPSIMULogger as GPSIMULogger
    from src.mocks.hardware_mocks import MockGPIOMonitor as GPIOMonitor

# El resto de los imports que son multiplataforma
from src.core.log_processor import process_pending_logs
from src.services.web_server import WebServer

class Application(tk.Tk):
    """
    Clase principal de la interfaz gráfica HUMS.
    Orquesta los diferentes módulos de la aplicación (loggers, servidor, etc.).
    """
    # --- Constantes de Estilo para replicar la apariencia original ---
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
        self.title("HUMS Interface")
        self.attributes('-fullscreen', True)  # Iniciar en pantalla completa
        self.configure(bg=self.BG_COLOR)

        # --- Backend/Lógica ---
        self.obd_logger = OBDLogger()
        self.gps_logger = GPSIMULogger()
        self.web_server = WebServer()
        self.gpio_monitor_thread = threading.Thread(target=GPIOMonitor().start, daemon=True)
        self.gpio_monitor_thread.start()

        # --- Estado y UI ---
        self.current_screen = None
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        logging.info("GUI de la aplicación HUMS inicializada.")

    def setup_ui(self):
        """Configura los elementos principales de la UI (header, sidebar, main_frame)."""
        # --- Header ---
        self.header = tk.Frame(self, bg=self.FRAME_BG_COLOR, height=60)
        self.header.pack(fill=tk.X, side=tk.TOP, padx=10, pady=10)
        self.header.pack_propagate(False)
        tk.Label(self.header, text="HUMS Interface", font=self.FONT_TITLE, bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT, padx=20)
        
        # --- Sidebar ---
        self.sidebar = tk.Frame(self, bg=self.SIDEBAR_BG_COLOR, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=(0, 10))
        self.sidebar.pack_propagate(False)

        sidebar_buttons = {
            "Archivos CSV": lambda: self._create_file_viewer_screen("Archivos CSV", config.CSV_EXPORTS_DIR),
            "Ver Logs Configuración": lambda: self._create_file_viewer_screen("Ver Logs Configuración", config.SYSTEM_LOG_DIR),
            "Ver Archivos de Logs": lambda: self._create_file_viewer_screen("Ver Archivos de Logs", config.CAN_LOG_DIR),
        }
        for text, command in sidebar_buttons.items():
            tk.Button(self.sidebar, text=text, font=self.FONT_BUTTON, bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=command, anchor="w").pack(pady=10, padx=10, fill=tk.X, ipady=5)

        # --- Main Frame ---
        self.main_frame = tk.Frame(self, bg=self.BG_COLOR)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.show_main_screen()

    def _clear_main_frame(self):
        """Limpia el frame principal antes de mostrar una nueva pantalla."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.current_screen = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        self.current_screen.pack(fill=tk.BOTH, expand=True)

    def _create_screen_header(self, title):
        """Crea un encabezado estándar para cada pantalla."""
        header_frame = tk.Frame(self.current_screen, bg=self.BG_COLOR)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(header_frame, text=f"<>  {title}", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack()
        return self.current_screen

    def _create_back_button(self):
        """Crea un botón estándar para volver al menú principal."""
        tk.Button(self.current_screen, text="< Volver a Inicio", font=self.FONT_BUTTON, bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=self.show_main_screen).pack(pady=20)

    # --- Pantallas Principales ---

    def show_main_screen(self):
        self._clear_main_frame()
        
        button_frame = tk.Frame(self.current_screen, bg=self.BG_COLOR)
        button_frame.pack(fill=tk.BOTH, expand=True, padx=50, pady=20)
        
        main_buttons = {
            "Información del Vehículo": self.show_vehicle_info,
            "Registro CAN": self.show_can_traffic,
            "Solicitudes": self.show_requests,
            "Comunicaciones": self.show_communications,
            "Configuración HUMS": self.show_hums_config,
            "Abrir Servidor": self.show_open_server,
            "WIFI": self.show_wifi,
            "IMU/GPS": self.show_imu_gps
        }
        for text, command in main_buttons.items():
            tk.Button(button_frame, text=text, font=("Noto Sans", 14, "bold"), bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat", command=command).pack(fill=tk.X, pady=8, ipady=10)

        # --- Footer con ID y Versión ---
        footer_frame = tk.Frame(self.current_screen, bg=self.BG_COLOR)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        try:
            with open(config.DEVICE_ID_FILE, "r") as f:
                device_id = f.read().strip()
        except FileNotFoundError:
            device_id = "No definido"
        
        tk.Label(footer_frame, text=f"Nº ID: {device_id}", font=self.FONT_NORMAL, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)
        tk.Label(footer_frame, text="Versión 2.0.0", font=self.FONT_NORMAL, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.RIGHT)

    def show_vehicle_info(self):
        self._clear_main_frame()
        container = self._create_screen_header("Información del Vehículo")

        # --- Sección de Control CAN ---
        can_control_frame = tk.Frame(container, bg=self.BG_COLOR)
        can_control_frame.pack(fill=tk.X, pady=10)
        tk.Label(can_control_frame, text="CAN Status:", font=self.FONT_NORMAL, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT, padx=(0, 5))
        self.vehicle_can_status = tk.Label(can_control_frame, text="INACTIVE", font=(self.FONT_NORMAL[0], self.FONT_NORMAL[1], 'bold'), bg=self.BG_COLOR, fg=self.ERROR_COLOR)
        self.vehicle_can_status.pack(side=tk.LEFT, padx=(0, 20))
        tk.Button(can_control_frame, text="Stop Logger", bg=self.ERROR_COLOR, fg=self.TEXT_COLOR, relief="flat", font=self.FONT_BUTTON).pack(side=tk.LEFT, padx=5)
        tk.Button(can_control_frame, text="Activar CAN", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat", font=self.FONT_BUTTON).pack(side=tk.LEFT, padx=5)

        # --- Secciones VIN, CVN, DTC ---
        for title in ["VIN del Vehículo", "CVN del Vehículo", "Códigos de Falla (DTCs)"]:
            lf = tk.LabelFrame(container, text=title, bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, bd=1, relief="solid", padx=10, pady=10)
            lf.pack(fill=tk.X, pady=10, padx=20)
            
            if "DTC" not in title:
                button_frame = tk.Frame(lf, bg=self.FRAME_BG_COLOR)
                button_frame.pack(pady=5)
                tk.Button(button_frame, text=f"Solicitar {title.split()[0]}", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)
                tk.Button(button_frame, text=f"Leer {title.split()[0]}", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)
                scrolledtext.ScrolledText(lf, height=2, bg=self.TEXT_COLOR, state="disabled").pack(fill=tk.X, pady=5)
            else:
                dtc_frame = tk.Frame(lf, bg=self.FRAME_BG_COLOR)
                dtc_frame.pack(fill=tk.X)
                tk.Label(dtc_frame, text="DTCs Almacenados:", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).grid(row=0, column=0, sticky="w", pady=2)
                tk.Button(dtc_frame, text="Solicitar", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").grid(row=0, column=1, padx=5)
                tk.Button(dtc_frame, text="Leer", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").grid(row=0, column=2, padx=5)
                tk.Label(dtc_frame, text="DTCs Pendientes:", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).grid(row=1, column=0, sticky="w", pady=2)
                tk.Button(dtc_frame, text="Solicitar", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").grid(row=1, column=1, padx=5)
                tk.Button(dtc_frame, text="Leer", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").grid(row=1, column=2, padx=5)
                scrolledtext.ScrolledText(lf, height=5, bg=self.SIDEBAR_BG_COLOR, fg=self.TEXT_COLOR, state="disabled").pack(fill=tk.X, pady=10)

        self._create_back_button()

    def show_can_traffic(self):
        self._clear_main_frame()
        container = self._create_screen_header("Registro CAN")

        main_paned_window = tk.PanedWindow(container, orient=tk.HORIZONTAL, bg=self.BG_COLOR, sashwidth=10)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=20)

        # --- Columna Izquierda ---
        left_frame = tk.Frame(main_paned_window, bg=self.BG_COLOR)
        
        # Velocidad CAN
        lf_speed = tk.LabelFrame(left_frame, text="Velocidad CAN", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_speed.pack(fill=tk.X, pady=5)
        tk.Label(lf_speed, text="Seleccionar velocidad:", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)
        ttk.Combobox(lf_speed, values=["500000", "250000", "125000"], state="readonly").pack(side=tk.LEFT, padx=5)
        tk.Button(lf_speed, text="Establecer", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)

        # Estado CAN y Control
        status_frame = tk.Frame(left_frame, bg=self.BG_COLOR)
        status_frame.pack(fill=tk.X, pady=10)
        tk.Label(status_frame, text="Estado CAN:", bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)
        tk.Label(status_frame, text="INACTIVO", bg=self.BG_COLOR, fg=self.ERROR_COLOR, font=(self.FONT_NORMAL[0], self.FONT_NORMAL[1], 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(status_frame, text="Activar CAN", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=10)
        tk.Button(status_frame, text="Stop CAN", bg=self.ERROR_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)

        # Filtros
        lf_filters = tk.LabelFrame(left_frame, text="Filtros", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_filters.pack(fill=tk.X, pady=5)
        tk.Checkbutton(lf_filters, text="Mostrar 7DF (Solicitudes)", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, selectcolor=self.BG_COLOR, activebackground=self.FRAME_BG_COLOR, activeforeground=self.TEXT_COLOR).pack(anchor="w")
        tk.Checkbutton(lf_filters, text="Mostrar 7E8 (Respuestas)", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, selectcolor=self.BG_COLOR, activebackground=self.FRAME_BG_COLOR, activeforeground=self.TEXT_COLOR).pack(anchor="w")

        # PIDs
        lf_pids = tk.LabelFrame(left_frame, text="Selección de PIDs", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_pids.pack(fill=tk.BOTH, expand=True, pady=5)
        # ... (Agregar checkbuttons de PIDs aquí)

        tk.Button(left_frame, text="Iniciar Registro", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat", font=self.FONT_BUTTON).pack(side=tk.LEFT, pady=10)
        tk.Button(left_frame, text="Detener Registro", bg=self.ERROR_COLOR, fg=self.TEXT_COLOR, relief="flat", font=self.FONT_BUTTON).pack(side=tk.LEFT, pady=10, padx=5)

        # --- Columna Derecha ---
        right_frame = tk.Frame(main_paned_window, bg=self.BG_COLOR)
        tk.Label(right_frame, text="Registro CAN:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON).pack(anchor="w")
        scrolledtext.ScrolledText(right_frame, height=20, bg=self.TEXT_COLOR).pack(fill=tk.BOTH, expand=True)

        main_paned_window.add(left_frame)
        main_paned_window.add(right_frame)

        self._create_back_button()

    def show_hums_config(self):
        self._clear_main_frame()
        container = self._create_screen_header("Configuración HUMS")
        
        content_frame = tk.Frame(container, bg=self.BG_COLOR, padx=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Fecha y Hora
        lf_date = tk.LabelFrame(content_frame, text="Configurar fecha y hora (yyyy-mm-dd HH:MM):", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_date.pack(fill=tk.X, pady=10)
        tk.Entry(lf_date).pack(side=tk.LEFT, padx=5)
        tk.Button(lf_date, text="Actualizar Fecha y Hora", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)

        # Bastidor
        lf_chassis = tk.LabelFrame(content_frame, text="Número de bastidor:", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_chassis.pack(fill=tk.X, pady=10)
        tk.Entry(lf_chassis).pack(side=tk.LEFT, padx=5)
        tk.Button(lf_chassis, text="Agregar Número de Bastidor", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)

        # Nombre
        lf_name = tk.LabelFrame(content_frame, text="Nombre:", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_name.pack(fill=tk.X, pady=10)
        tk.Entry(lf_name).pack(side=tk.LEFT, padx=5)
        tk.Button(lf_name, text="Agregar Nombre", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)

        # Estado de servicios
        lf_services = tk.LabelFrame(content_frame, text="Estado de los servicios", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_services.pack(fill=tk.BOTH, expand=True, pady=10)
        scrolledtext.ScrolledText(lf_services, height=5, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(fill=tk.BOTH, expand=True)

        # Botones de acción
        action_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        action_frame.pack(pady=10)
        tk.Button(action_frame, text="Verificar Servicios", bg=self.INFO_COLOR, fg=self.TEXT_COLOR, relief="flat", font=self.FONT_BUTTON).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="Finalizar", bg=self.ERROR_COLOR, fg=self.TEXT_COLOR, relief="flat", font=self.FONT_BUTTON).pack(side=tk.LEFT, padx=5)

        self._create_back_button()

    def show_imu_gps(self):
        self._clear_main_frame()
        container = self._create_screen_header("IMU/GPS")
        
        status_frame = tk.Frame(container, bg=self.BG_COLOR)
        status_frame.pack(fill=tk.X, pady=20, padx=20)
        tk.Label(status_frame, text="Estado:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON).pack(side=tk.LEFT)
        self.gps_status_label = tk.Label(status_frame, text="INACTIVO", bg=self.BG_COLOR, fg=self.ERROR_COLOR, font=(self.FONT_BUTTON[0], self.FONT_BUTTON[1], 'bold'))
        self.gps_status_label.pack(side=tk.LEFT, padx=10)

        button_frame = tk.Frame(container, bg=self.BG_COLOR)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Reiniciar Sensores", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=10)
        self.gps_toggle_button = tk.Button(button_frame, text="Activar GPS", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat", command=self.toggle_gps_logger)
        self.gps_toggle_button.pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Ver Datos", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=10)

        warning_frame = tk.LabelFrame(container, bg=self.FRAME_BG_COLOR, bd=1, relief="solid")
        warning_frame.pack(fill=tk.X, pady=20, padx=20, ipady=5)
        tk.Label(warning_frame, text="! ANTES DE ACTIVAR EL GPS, ASEGURARSE DE QUE ESTÁ CONECTADO", bg=self.FRAME_BG_COLOR, fg="#fbbf24", font=("Noto Sans", 10, "bold")).pack()
        
        self.update_gps_ui()
        self._create_back_button()

    def show_open_server(self):
        self._clear_main_frame()
        container = self._create_screen_header("Abrir Servidor")
        
        lf_info = tk.LabelFrame(container, text="Información del Servidor", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
        lf_info.pack(fill=tk.X, padx=20, pady=20)
        
        info_text = f"IP: <IP de la RPi>    Puerto: {config.WEB_SERVER_PORT}\nRuta: {config.CSV_EXPORTS_DIR}"
        tk.Label(lf_info, text=info_text, justify=tk.LEFT, bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).pack(anchor="w")
        
        status_frame = tk.Frame(container, bg=self.BG_COLOR)
        status_frame.pack(pady=10)
        tk.Label(status_frame, text="Estado:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON).pack(side=tk.LEFT)
        self.server_status_label = tk.Label(status_frame, text="DETENIDO", bg=self.BG_COLOR, fg=self.ERROR_COLOR, font=(self.FONT_BUTTON[0], self.FONT_BUTTON[1], 'bold'))
        self.server_status_label.pack(side=tk.LEFT, padx=10)
        
        button_frame = tk.Frame(container, bg=self.BG_COLOR)
        button_frame.pack(pady=10)
        self.server_toggle_button = tk.Button(button_frame, text="Iniciar Servidor", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat", command=self.toggle_web_server)
        self.server_toggle_button.pack()
        
        self.update_server_ui()
        self._create_back_button()

    def show_communications(self):
        self._clear_main_frame()
        container = self._create_screen_header("Comunicaciones")
        
        for comm_type in ["RS232", "RS485"]:
            lf = tk.LabelFrame(container, text=f"Comunicación {comm_type}", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_BUTTON, padx=10, pady=10)
            lf.pack(fill=tk.X, padx=20, pady=10)
            
            control_frame = tk.Frame(lf, bg=self.FRAME_BG_COLOR)
            control_frame.pack(fill=tk.X, pady=5)
            tk.Button(control_frame, text="Activar", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT)
            tk.Button(control_frame, text="Desactivar", bg=self.ERROR_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)
            tk.Label(control_frame, text="Estado:", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT, padx=(20, 5))
            tk.Label(control_frame, text="INACTIVO", bg=self.FRAME_BG_COLOR, fg=self.ERROR_COLOR, font=(self.FONT_NORMAL[0], self.FONT_NORMAL[1], 'bold')).pack(side=tk.LEFT)

            msg_frame = tk.Frame(lf, bg=self.FRAME_BG_COLOR)
            msg_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            tk.Label(msg_frame, text="Mensajes Recibidos", bg=self.FRAME_BG_COLOR, fg=self.TEXT_COLOR).pack(anchor="w")
            scrolledtext.ScrolledText(msg_frame, height=4, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Button(msg_frame, text="Limpiar Mensajes", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=10, anchor="n")

        self._create_back_button()

    # --- Placeholders para pantallas futuras ---
    def show_requests(self):
        self._clear_main_frame()
        container = self._create_screen_header("Solicitudes")
        tk.Label(container, text="Pantalla en construcción...", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=50)
        self._create_back_button()
        
    def show_wifi(self):
        self._clear_main_frame()
        container = self._create_screen_header("WIFI")
        tk.Label(container, text="Pantalla en construcción...", font=self.FONT_HEADER, bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=50)
        self._create_back_button()

    # --- Visor de Archivos Genérico ---
    def _create_file_viewer_screen(self, title, target_directory):
        self._clear_main_frame()
        container = self._create_screen_header(title)

        tk.Label(container, text=f"Ruta: {target_directory}", bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(pady=5)

        tree_frame = tk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        columns = ("name", "size", "date")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        tree.heading("name", text="Nombre del Archivo")
        tree.heading("size", text="Tamaño")
        tree.heading("date", text="Fecha Modificación")
        tree.column("name", width=350)
        tree.column("size", width=100, anchor="e")
        tree.column("date", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = tk.Frame(container, bg=self.BG_COLOR)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Abrir", bg=self.SUCCESS_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Eliminar", bg=self.ERROR_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Actualizar Lista", bg=self.BUTTON_BG_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Copiar a USB", bg=self.INFO_COLOR, fg=self.TEXT_COLOR, relief="flat").pack(side=tk.LEFT, padx=5)

        self._create_back_button()

    # --- Lógica de Control y Actualización de UI ---

    def toggle_gps_logger(self):
        if self.gps_logger.is_running():
            self.gps_logger.stop()
        else:
            self.gps_logger.start()
        self.update_gps_ui()
    
    def update_gps_ui(self):
        if self.gps_logger.is_running():
            self.gps_status_label.config(text="ACTIVO", fg=self.SUCCESS_COLOR)
            self.gps_toggle_button.config(text="Desactivar GPS", bg=self.ERROR_COLOR)
        else:
            self.gps_status_label.config(text="INACTIVO", fg=self.ERROR_COLOR)
            self.gps_toggle_button.config(text="Activar GPS", bg=self.SUCCESS_COLOR)

    def toggle_web_server(self):
        if self.web_server.is_running():
            self.web_server.stop()
        else:
            self.web_server.start()
        self.update_server_ui()

    def update_server_ui(self):
        if self.web_server.is_running():
            self.server_status_label.config(text="EJECUTANDO", fg=self.SUCCESS_COLOR)
            self.server_toggle_button.config(text="Detener Servidor", bg=self.ERROR_COLOR)
        else:
            self.server_status_label.config(text="DETENIDO", fg=self.ERROR_COLOR)
            self.server_toggle_button.config(text="Iniciar Servidor", bg=self.SUCCESS_COLOR)

    def on_closing(self):
        """Maneja el evento de cierre de la ventana."""
        if messagebox.askokcancel("Salir", "¿Seguro que quieres salir? Se detendrán todos los servicios."):
            logging.info("Cerrando aplicación y deteniendo servicios...")
            if self.obd_logger.is_running(): self.obd_logger.stop()
            if self.gps_logger.is_running(): self.gps_logger.stop()
            if self.web_server.is_running(): self.web_server.stop()
            self.destroy()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app = Application()
    app.mainloop()