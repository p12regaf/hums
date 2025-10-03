# ./src/services/web_server.py
import os
import cgi
import html
import shutil
import socket
import math
import logging
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from socketserver import TCPServer

import config

# Plantilla para el handler. Leemos el template una sola vez al iniciar.
try:
    TEMPLATE_PATH = os.path.join(config.ASSETS_DIR, "templates", "web_server_template.html")
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        HTML_TEMPLATE = f.read()
except FileNotFoundError:
    logging.critical(f"No se encontró el archivo de plantilla del servidor web en {TEMPLATE_PATH}. El servidor no funcionará.")
    HTML_TEMPLATE = "<html><body><h1>Error: Template not found</h1></body></html>"

class _CustomHandler(SimpleHTTPRequestHandler):
    """
    Handler personalizado que sirve archivos, gestiona subidas/descargas
    y muestra una interfaz web con paginación.
    """
    FILES_PER_PAGE = 15

    def __init__(self, *args, **kwargs):
        # El directorio se pasa al handler para asegurar que siempre sirve desde la ubicación correcta.
        super().__init__(*args, directory=config.CSV_EXPORTS_DIR, **kwargs)

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/list'):
            self.list_directory()
        elif self.path.startswith('/download/'):
            # Decodifica el nombre del archivo para manejar espacios y caracteres especiales
            file_to_download = unquote(self.path[len('/download/'):])
            self.download_file(file_to_download)
        else:
            # Para cualquier otro archivo, usa el comportamiento por defecto (servir el archivo si existe)
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/delete/'):
            file_to_delete = unquote(self.path[len('/delete/'):])
            self.delete_file(file_to_delete)
        elif self.path == '/upload':
            self.upload_file()
        else:
            self.send_error(405, "Método no permitido")

    def list_directory(self):
        """Genera y sirve la página HTML con la lista de archivos."""
        try:
            all_files = sorted(os.listdir(self.directory), key=str.lower)
            
            query = parse_qs(urlparse(self.path).query)
            page = int(query.get('page', ['1'])[0])
            
            start_index = (page - 1) * self.FILES_PER_PAGE
            end_index = start_index + self.FILES_PER_PAGE
            files_on_page = all_files[start_index:end_index]

            file_list_html = self.generate_file_list_html(files_on_page)
            pagination_html = self.generate_pagination_html(len(all_files), page)
            
            # Reemplazar placeholders en la plantilla
            content = HTML_TEMPLATE.replace('{{FILE_LIST_PLACEHOLDER}}', file_list_html)
            content = content.replace('{{PAGINATION_PLACEHOLDER}}', pagination_html)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            
        except FileNotFoundError:
            self.send_error(404, "Directorio no encontrado")
        except Exception as e:
            logging.error(f"Error al listar el directorio: {e}")
            self.send_error(500, "Error interno del servidor")

    def generate_file_list_html(self, files):
        items = []
        for name in files:
            encoded_name = html.escape(name)
            items.append(f"""
                <li class="file-list-item">
                    <span>{encoded_name}</span>
                    <div class="button-container">
                        <a href="/download/{encoded_name}" class="button download">Descargar</a>
                        <form action="/delete/{encoded_name}" method="post" onsubmit="return confirm('¿Seguro que quieres borrar este archivo?');">
                            <button type="submit" class="button delete">Borrar</button>
                        </form>
                    </div>
                </li>
            """)
        return '<ul class="file-list">' + ''.join(items) + '</ul>' if items else "<p>No hay archivos en este directorio.</p>"

    def generate_pagination_html(self, total_files, current_page):
        total_pages = math.ceil(total_files / self.FILES_PER_PAGE)
        if total_pages <= 1:
            return ""
        
        pagination = '<div class="pagination">'
        if current_page > 1:
            pagination += f'<a href="/list?page={current_page - 1}" class="previous">&laquo; Anterior</a>'
        
        pagination += f'<span>Página {current_page} de {total_pages}</span>'

        if current_page < total_pages:
            pagination += f'<a href="/list?page={current_page + 1}" class="next">Siguiente &raquo;</a>'
        pagination += '</div>'
        return pagination

    def download_file(self, filename):
        file_path = os.path.join(self.directory, filename)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
                    fs = os.fstat(f.fileno())
                    self.send_header("Content-Length", str(fs.st_size))
                    self.end_headers()
                    shutil.copyfileobj(f, self.wfile)
            except Exception as e:
                logging.error(f"Error al descargar {filename}: {e}")
                self.send_error(500, "No se pudo leer el archivo")
        else:
            self.send_error(404, "Archivo no encontrado")

    def delete_file(self, filename):
        file_path = os.path.join(self.directory, filename)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Archivo eliminado: {file_path}")
                self.send_response(303) # 303 See Other, para redirigir tras un POST
                self.send_header('Location', '/list')
                self.end_headers()
            except Exception as e:
                logging.error(f"Error al eliminar {filename}: {e}")
                self.send_error(500, "No se pudo eliminar el archivo")
        else:
            self.send_error(404, "Archivo no encontrado")

    def upload_file(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']}
        )
        if 'file' in form:
            file_item = form['file']
            if file_item.filename:
                filename = os.path.basename(file_item.filename)
                file_path = os.path.join(self.directory, filename)
                try:
                    with open(file_path, 'wb') as f:
                        f.write(file_item.file.read())
                    logging.info(f"Archivo subido: {file_path}")
                    self.send_response(303)
                    self.send_header('Location', '/list')
                    self.end_headers()
                except Exception as e:
                    logging.error(f"Error al guardar archivo subido {filename}: {e}")
                    self.send_error(500, "Error al guardar el archivo")
            else:
                self.send_error(400, "No se proporcionó un nombre de archivo")
        else:
            self.send_error(400, "No se subió ningún archivo")


class WebServer:
    """
    Clase contenedora para el servidor HTTP que se ejecuta en un hilo.
    """
    def __init__(self):
        self.port = config.WEB_SERVER_PORT
        self._server = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            logging.warning("El servidor web ya está en ejecución.")
            return

        try:
            self._server = TCPServer(("", self.port), _CustomHandler)
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logging.info(f"Servidor web iniciado en http://0.0.0.0:{self.port}")
        except OSError as e:
            logging.error(f"No se pudo iniciar el servidor en el puerto {self.port}: {e}")
            self._server = None
            self._running = False

    def _run(self):
        if self._server:
            self._server.serve_forever()
        logging.info("El bucle del servidor web ha finalizado.")


    def stop(self):
        if not self._running or not self._server:
            logging.warning("El servidor web no está en ejecución.")
            return

        logging.info("Deteniendo el servidor web...")
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        self._running = False
        logging.info("Servidor web detenido.")
        
    def is_running(self):
        return self._running