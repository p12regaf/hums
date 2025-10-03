# ./src/gui/app.py
# NOTA: Este es un refactoring muy extenso. Se han simplificado algunas partes
# para demostrar el patrón de diseño. Puede que necesites ajustar detalles específicos.

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import threading
import queue
import os
import logging

# Importamos la configuración y los módulos de lógica
import config
from src.core.obd_logger import OBDLogger
from src.core.gps_imu_logger import GPSIMULogger
from src.core.log_processor import process_pending_logs
from src.services.web_server import WebServer
from src.services.gpio_monitor import GPIOMonitor

class Application(tk.Tk):
    """
    Clase principal de la interfaz gráfica HUMS.
    Orquesta los diferentes módulos de la aplicación (loggers, servidor, etc.).
    """
    def __init__(self):
        super().__init__()
        self.title("HUMS Interface v3.0 (Refactored)")
        self.geometry("1024x768")
        self.configure(bg="#1e293b")

        # --- Backend/Lógica ---
        # Instanciamos los controladores de la lógica de negocio.
        # La GUI solo los llamará, no contendrá su lógica.
        self.obd_logger = OBDLogger()
        self.gps_logger = GPSIMULogger()
        self.web_server = WebServer()
        # El monitor GPIO es especial, lo lanzamos en un hilo que se gestionará a sí mismo.
        self.gpio_monitor_thread = threading.Thread(target=GPIOMonitor().start, daemon=True)
        self.gpio_monitor_thread.start()

        # Cola para comunicar datos del logger OBD a la GUI de forma segura
        self.can_traffic_queue = queue.Queue()

        # --- Estado y UI ---
        self.current_screen = None
        self.setup_ui()
        
        # Iniciar el bucle para actualizar la UI desde la cola
        self.update_can_traffic_display()

        # Asegurarse de que los hilos se detengan al cerrar la ventana
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        logging.info("GUI de la aplicación HUMS inicializada.")

    def setup_ui(self):
        """Configura los elementos principales de la UI (header, sidebar, main_frame)."""
        self.header = tk.Frame(self, bg="#334155", height=50)
        self.header.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(10,0))
        tk.Label(self.header, text="HUMS Interface", font=("Noto Sans", 20, "bold"), bg="#334155", fg="white").pack(side=tk.LEFT, padx=20)

        self.sidebar = tk.Frame(self, bg="#475569", width=200, padx=10, pady=10)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10,0), pady=10)

        self.main_frame = tk.Frame(self, bg="#1e293b", padx=20, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Crear botones de la barra lateral
        buttons = {
            "Inicio": self.show_main_screen,
            "Logger OBD": self.show_obd_logger_screen,
            "Logger GPS/IMU": self.show_gps_logger_screen,
            "Procesar Logs": self.show_log_processor_screen,
            "Servidor Web": self.show_web_server_screen,
        }
        for text, command in buttons.items():
            tk.Button(self.sidebar, text=text, font=("Noto Sans", 14), bg="#64748b", fg="white", 
                      relief="flat", command=command).pack(pady=10, fill=tk.X)

        self.show_main_screen()

    def show_screen_frame(self, title):
        """Limpia el frame principal y prepara un nuevo contenedor con un título."""
        if self.current_screen:
            self.current_screen.destroy()
        
        self.current_screen = tk.Frame(self.main_frame, bg="#1e293b")
        self.current_screen.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(self.current_screen, text=title, font=("Poppins", 18, "bold"), 
                 bg="#334155", fg="white", pady=10).pack(fill=tk.X)
        
        return self.current_screen

    def show_main_screen(self):
        """Muestra la pantalla de bienvenida."""
        container = self.show_screen_frame("Panel de Control Principal")
        tk.Label(container, text="Bienvenido al Sistema de Monitoreo HUMS.",
                 font=("Noto Sans", 14), bg="#1e293b", fg="white").pack(pady=20)
        
        # Aquí se podría añadir un resumen del estado de los servicios.

    def show_obd_logger_screen(self):
        """Muestra la pantalla para controlar el Logger OBD."""
        container = self.show_screen_frame("Control del Logger OBD")
        
        # Frame de control
        control_frame = tk.Frame(container, bg="#1e293b")
        control_frame.pack(pady=20)
        
        self.obd_status_label = tk.Label(control_frame, text="Estado: Detenido", font=("Noto Sans", 12), bg="#1e293b", fg="#ef4444")
        self.obd_status_label.pack(side=tk.LEFT, padx=10)

        self.obd_toggle_btn = tk.Button(control_frame, text="Iniciar Logger", command=self.toggle_obd_logger)
        self.obd_toggle_btn.pack(side=tk.LEFT, padx=10)
        
        # Área de texto para el tráfico
        self.can_traffic_text = scrolledtext.ScrolledText(container, wrap=tk.WORD, bg="#0f172a", fg="cyan", state="disabled")
        self.can_traffic_text.pack(fill=tk.BOTH, expand=True, pady=10)

        self.update_obd_logger_ui()

    def toggle_obd_logger(self):
        """Inicia o detiene el logger OBD."""
        if self.obd_logger.is_running():
            self.obd_logger.stop()
        else:
            self.obd_logger.start()
        self.update_obd_logger_ui()

    def update_obd_logger_ui(self):
        """Actualiza la UI del logger OBD según su estado."""
        if self.obd_logger.is_running():
            self.obd_status_label.config(text="Estado: En Ejecución", fg="#22c55e")
            self.obd_toggle_btn.config(text="Detener Logger")
        else:
            self.obd_status_label.config(text="Estado: Detenido", fg="#ef4444")
            self.obd_toggle_btn.config(text="Iniciar Logger")

    def update_can_traffic_display(self):
        """Saca mensajes de la cola y los muestra en el ScrolledText."""
        try:
            while not self.can_traffic_queue.empty():
                message = self.can_traffic_queue.get_nowait()
                self.can_traffic_text.config(state="normal")
                self.can_traffic_text.insert(tk.END, message + "\n")
                self.can_traffic_text.see(tk.END)
                self.can_traffic_text.config(state="disabled")
        except queue.Empty:
            pass
        
        # Vuelve a llamar a esta función después de 100ms
        self.after(100, self.update_can_traffic_display)

    def show_gps_logger_screen(self):
        """Muestra la pantalla para controlar el Logger GPS/IMU."""
        container = self.show_screen_frame("Control del Logger GPS/IMU")
        
        self.gps_status_label = tk.Label(container, text="Estado: Detenido", font=("Noto Sans", 12), bg="#1e293b", fg="#ef4444")
        self.gps_status_label.pack(pady=10)

        self.gps_toggle_btn = tk.Button(container, text="Iniciar Logger", command=self.toggle_gps_logger)
        self.gps_toggle_btn.pack(pady=10)
        
        self.update_gps_logger_ui()

    def toggle_gps_logger(self):
        if self.gps_logger.is_running():
            self.gps_logger.stop()
        else:
            self.gps_logger.start()
        self.update_gps_logger_ui()

    def update_gps_logger_ui(self):
        if self.gps_logger.is_running():
            self.gps_status_label.config(text="Estado: En Ejecución", fg="#22c55e")
            self.gps_toggle_btn.config(text="Detener Logger")
        else:
            self.gps_status_label.config(text="Estado: Detenido", fg="#ef4444")
            self.gps_toggle_btn.config(text="Iniciar Logger")
            
    def show_log_processor_screen(self):
        """Muestra la pantalla para procesar logs."""
        container = self.show_screen_frame("Procesador de Logs (DBC a CSV)")
        
        tk.Button(container, text="Procesar Logs Pendientes", command=self.run_log_processor).pack(pady=20)
        
        self.log_processor_status = tk.Label(container, text="", font=("Noto Sans", 12), bg="#1e293b", fg="white")
        self.log_processor_status.pack(pady=10)

    def run_log_processor(self):
        """Ejecuta el procesador de logs en un hilo para no bloquear la GUI."""
        def target():
            self.log_processor_status.config(text="Procesando...", fg="yellow")
            try:
                process_pending_logs()
                self.log_processor_status.config(text="Proceso completado.", fg="#22c55e")
            except Exception as e:
                logging.error(f"Error al procesar logs desde la GUI: {e}")
                self.log_processor_status.config(text=f"Error: {e}", fg="#ef4444")
        
        threading.Thread(target=target, daemon=True).start()

    def show_web_server_screen(self):
        """Muestra la pantalla para controlar el Servidor Web."""
        container = self.show_screen_frame("Control del Servidor Web")

        self.server_status_label = tk.Label(container, text="Estado: Detenido", font=("Noto Sans", 12), bg="#1e293b", fg="#ef4444")
        self.server_status_label.pack(pady=10)
        
        tk.Label(container, text=f"Accede en: http://<IP_RASPBERRY>:{config.WEB_SERVER_PORT}", 
                 font=("Noto Sans", 10), bg="#1e293b", fg="white").pack()

        self.server_toggle_btn = tk.Button(container, text="Iniciar Servidor", command=self.toggle_web_server)
        self.server_toggle_btn.pack(pady=20)
        
        self.update_web_server_ui()

    def toggle_web_server(self):
        if self.web_server.is_running():
            self.web_server.stop()
        else:
            self.web_server.start()
        self.update_web_server_ui()

    def update_web_server_ui(self):
        if self.web_server.is_running():
            self.server_status_label.config(text="Estado: En Ejecución", fg="#22c55e")
            self.server_toggle_btn.config(text="Detener Servidor")
        else:
            self.server_status_label.config(text="Estado: Detenido", fg="#ef4444")
            self.server_toggle_btn.config(text="Iniciar Servidor")
            
    def on_closing(self):
        """Maneja el evento de cierre de la ventana."""
        if messagebox.askokcancel("Salir", "¿Seguro que quieres salir? Se detendrán todos los servicios."):
            logging.info("Cerrando aplicación y deteniendo servicios...")
            if self.obd_logger.is_running():
                self.obd_logger.stop()
            if self.gps_logger.is_running():
                self.gps_logger.stop()
            if self.web_server.is_running():
                self.web_server.stop()
            
            self.destroy()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = Application()
    app.mainloop()