# ./src/services/gpio_monitor.py
import RPi.GPIO as GPIO
import subprocess
import logging
import signal
import time
import config

class GPIOMonitor:
    """
    Monitorea pines GPIO para eventos específicos como el apagado del sistema.
    """
    def __init__(self):
        self.shutdown_pins = {
            config.SHUTDOWN_PIN_1: GPIO.HIGH, # Pin 37 se activa en alto
            config.SHUTDOWN_PIN_2: GPIO.LOW   # Pin 36 se activa en bajo
        }
        self._running = False
        logging.info("Monitor GPIO inicializado.")

    def _handle_shutdown(self, channel):
        """Callback que se ejecuta cuando se detecta un evento de apagado."""
        # Pequeño debounce por software
        time.sleep(0.5)
        
        # Comprobar de nuevo el estado para evitar falsos positivos
        pin_state = GPIO.input(channel)
        expected_state = self.shutdown_pins[channel]

        if pin_state == expected_state:
            logging.warning(f"Señal de apagado detectada en el pin {channel}. Apagando el sistema.")
            try:
                subprocess.call(['sudo', 'shutdown', 'now'])
            except Exception as e:
                logging.error(f"Error al intentar apagar el sistema: {e}")

    def start(self):
        """Configura los eventos GPIO y comienza a escuchar."""
        if self._running:
            logging.warning("El monitor GPIO ya está en ejecución.")
            return

        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setwarnings(False)

            for pin, trigger_state in self.shutdown_pins.items():
                pull_resistor = GPIO.PUD_DOWN if trigger_state == GPIO.HIGH else GPIO.PUD_UP
                edge_detection = GPIO.RISING if trigger_state == GPIO.HIGH else GPIO.FALLING
                
                GPIO.setup(pin, GPIO.IN, pull_up_down=pull_resistor)
                GPIO.add_event_detect(pin, edge_detection, callback=self._handle_shutdown, bouncetime=2000)
                logging.info(f"Escuchando eventos de apagado en el pin {pin} (activación en estado {'ALTO' if trigger_state else 'BAJO'}).")

            self._running = True
            logging.info("Monitor GPIO iniciado y escuchando eventos.")
            # Mantenemos el hilo vivo esperando una señal
            signal.pause()

        except Exception as e:
            logging.error(f"Error al iniciar el monitor GPIO: {e}")
            self.stop()

    def stop(self):
        """Limpia la configuración GPIO."""
        if self._running:
            logging.info("Deteniendo el monitor GPIO.")
            GPIO.cleanup()
            self._running = False

# Ejemplo de uso (esto sería llamado desde la GUI o main)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    monitor = GPIOMonitor()
    
    def signal_handler(sig, frame):
        monitor.stop()
        print("\nMonitor GPIO detenido limpiamente.")
        exit(0)

    signal.signal(signal.SIGINT, signal_handler) # Capturar Ctrl+C
    monitor.start()