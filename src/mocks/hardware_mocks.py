# ./src/mocks/hardware_mocks.py
import time
import threading
import logging

class MockOBDLogger:
    def __init__(self): self._running = False
    def start(self):
        logging.info("[MOCK] OBD Logger iniciado.")
        self._running = True
    def stop(self):
        logging.info("[MOCK] OBD Logger detenido.")
        self._running = False
    def is_running(self): return self._running

class MockGPSIMULogger:
    def __init__(self): self._running = False
    def start(self):
        logging.info("[MOCK] GPS/IMU Logger iniciado.")
        self._running = True
    def stop(self):
        logging.info("[MOCK] GPS/IMU Logger detenido.")
        self._running = False
    def is_running(self): return self._running

class MockGPIOMonitor:
    def start(self):
        logging.info("[MOCK] GPIO Monitor iniciado. No hará nada en Windows.")
        # En un mock, no necesitamos un bucle infinito, solo simular que está "activo"
        pass