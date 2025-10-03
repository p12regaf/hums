# ./main.py
import sys
import os
import logging
from src.gui.app import Application
import config

# Configurar logging básico para depuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Punto de entrada principal para la aplicación HUMS.
    """
    logging.info("Iniciando la aplicación HUMS...")

    # 1. Asegurar que los directorios de datos existen
    try:
        config.setup_directories()
    except Exception as e:
        logging.error(f"No se pudo crear la estructura de directorios: {e}")
        sys.exit(1)

    # 2. Iniciar la interfaz gráfica de usuario
    # La GUI será responsable de iniciar y gestionar los hilos de los servicios
    # como el logger OBD, el monitor GPIO, etc.
    try:
        app = Application()
        app.mainloop()
    except Exception as e:
        logging.critical(f"Error fatal en la aplicación de la GUI: {e}", exc_info=True)
        sys.exit(1)

    logging.info("Aplicación HUMS finalizada.")


if __name__ == "__main__":
    # Asegurarse de que el script se ejecuta como el usuario correcto si es necesario
    # (Aunque esto es mejor gestionarlo con systemd)
    if os.geteuid() == 0:
        print("Advertencia: Se recomienda no ejecutar la aplicación principal como root.")

    main()