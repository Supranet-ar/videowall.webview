import os
import socket
import sys
import threading
import time
import psutil
import webview
import logging
from screeninfo import get_monitors
import netifaces as ni

class WebViewWindow:
    def __init__(self):
        self.keep_running = True
        self.current_url = "http://supranet.ar/carteleria/lomoro-x4/"
        self.error_url = f"file://{os.path.join(os.path.dirname(__file__), 'error.html')}"

        # Limpiar el archivo de registro cada vez que se inicia el programa
        with open('webview_errors.log', 'w'):
            pass

        # Configurar el formato del registro de errores
        logging.basicConfig(filename='webview_errors.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

        # Obtener la dirección IP del dispositivo
        ip = self.get_local_ip()

        # Obtener información sobre las pantallas
        monitors = get_monitors()

        # Obtener el ancho y alto total de todas las pantallas
        total_width = sum(monitor.width for monitor in monitors)
        total_height = max(monitor.height for monitor in monitors)

        # Obtener la posición de la pantalla principal
        primary_monitor = next((monitor for monitor in monitors if monitor.is_primary), None)
        if primary_monitor:
            x, y = primary_monitor.x, primary_monitor.y
        else:
            # Si no se detecta una pantalla principal, usar la primera pantalla como referencia
            x, y = monitors[0].x, monitors[0].y

        # Configurar la ventana para abarcar todas las pantallas desde la posición de la pantalla principal
        self.window = webview.create_window("WebView Window", width=total_width, height=total_height, url=self.current_url, frameless=True, x=x, y=y)

        # Iniciar el servidor socket en un hilo
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((ip, 12345))
        self.server_socket.listen(5)
        self.socket_thread = threading.Thread(target=self.listen_for_urls, daemon=True)
        self.socket_thread.start()

        # Iniciar temporizador para refrescar el WebView cada minuto
        self.refresh_timer = threading.Timer(60, self.refresh_webview)
        self.refresh_timer.start()

        # Iniciar la detección de cambios de conectividad de red en un hilo separado
        self.network_thread = threading.Thread(target=self.monitor_network_changes, daemon=True)
        self.network_thread.start()

    def get_local_ip(self):
        interfaces = ni.interfaces()
        for interface in interfaces:
            try:
                ip = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
                return ip
            except KeyError:
                pass
        raise Exception("No se pudo encontrar una interfaz de red con una dirección IP asignada.")

    def listen_for_urls(self):
        while self.keep_running:
            try:
                client_socket, addr = self.server_socket.accept()
                data = client_socket.recv(1024).decode('utf-8').strip()

                if data == "exit":
                    logging.info("Instrucción de cierre recibida. Cerrando el socket y la ventana.")
                    self.window.destroy()
                    self.keep_running = False  # Establecer keep_running en False para detener otros bucles
                elif data:  # Verificar si se recibe una URL
                    logging.info(f"Recibida URL: {data}")
                    self.current_url = data  # Actualizar la URL actual
                    self.refresh_webview()

                client_socket.close()
            except OSError:
                break  # Salir del bucle si se produce un error de socket

    def refresh_webview(self):
        try:
            if self.check_internet_connection():
                self.window.load_url(self.current_url)
            else:
                self.window.load_url(self.error_url)
        except Exception as e:
            # Registrar el error en el archivo de registro
            logging.error(f"Error al refrescar el WebView: {e}", exc_info=True)

        # Cancelar el temporizador existente antes de iniciar uno nuevo
        if self.refresh_timer.is_alive():
            self.refresh_timer.cancel()

        # Iniciar un nuevo temporizador para la próxima actualización
        self.refresh_timer = threading.Timer(60, self.refresh_webview)
        self.refresh_timer.start()

    def monitor_network_changes(self):
        initial_status = psutil.net_if_stats()
        while self.keep_running:
            time.sleep(1)
            current_status = psutil.net_if_stats()
            # Verificar si hay algún cambio en el estado de la red
            if current_status != initial_status:
                logging.info("Se detectó un cambio en la conectividad de red")
                # Ejecutar el método refresh_webview() en respuesta al cambio de conectividad
                self.refresh_webview()
                initial_status = current_status  # Actualizar el estado inicial de la red

    def check_internet_connection(self):
        try:
            import requests
            requests.get("http://www.google.com", timeout=5)
            return True
        except:
            return False

    def stop_threads(self):
        self.keep_running = False
        self.server_socket.close()  # Cerrar el socket
        self.refresh_timer.cancel()  # Detener el temporizador de refresco
        self.socket_thread.join()  # Esperar a que el hilo del socket termine
        self.network_thread.join()  # Esperar a que el hilo de detección de red termine

if __name__ == '__main__':
    window = WebViewWindow()
    try:
        webview.start()
    except Exception as e:
        # Registrar el error en el archivo de registro
        logging.error(f"Se produjo un error: {e}", exc_info=True)
    finally:
        window.stop_threads()
        sys.exit(1)  # Salir del programa con un código de error
