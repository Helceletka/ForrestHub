import logging
import sys
import webbrowser
import click
import threading
import ssl
from app.init import create_app, socketio
from config import Config
from pathlib import Path
from app.utils import is_port_free, find_free_port, setup_logging

logger = logging.getLogger(__name__)
__version__ = (Path(__file__).parent / "VERSION").read_text().strip()

def run_flask(config: object | str, host="0.0.0.0", port=4444, ssl_context=None):
    """Spustí Flask server na HTTP nebo HTTPS."""
    app = create_app(config, ssl_context)
    socketio.run(
        app,
        host=host,
        port=port,
        use_reloader=config.USE_RELOADER,
        debug=config.DEBUG,
    )

@click.command(name="ForrestHub")
@click.option('--port', help='Port to run the server on')
@click.option('--host', help='Host address to bind the server')
@click.option('--host-qr', help='Host address shown in QR code in Admin panel')
@click.option('--version', is_flag=True, help='Show the version from setup.py')
def main(port, host, host_qr, version):
    config = Config()
    logger = setup_logging(config.EXECUTABLE_DIR, config.LOG_FOLDER)
    logging.basicConfig(level=logging.INFO)

    if version:
        print(f"ForrestHub App {__version__}")
        print("Pro více informací navštivte https://forresthub.helceletka.cz")
        sys.exit(0)

    if port:
        config.PORT = int(port)

    if host:
        config.HOST = host

    if host_qr:
        config.HOST_QR = host_qr

    if not is_port_free(config.HOST, config.PORT):
        new_port = find_free_port(config.HOST, 4444)
        logger.warning(f"Port {config.PORT} je již používán, přepínám na další dostupný port: {new_port}")
        config.PORT = new_port

    # HTTPS port
    https_port = 4433
    if not is_port_free(config.HOST, https_port):
        https_port = find_free_port(config.HOST, 4433)

    local_http = f"http://{config.HOST}:{config.PORT}"
    local_https = f"https://{config.HOST}:{https_port}"

    try:
        if config.FROZEN:
            webbrowser.open(local_http)
            webbrowser.open(f"{local_http}/admin")

        logger.info(f"Server byl spuštěn na adrese: {local_http} (HTTP)")
        logger.info(f"Server byl spuštěn na adrese: {local_https} (HTTPS)")
        logger.info("Press Ctrl-C to stop the server")

        # Spuštění HTTP serveru ve vlákně
        thread_http = threading.Thread(target=run_flask, args=(config, config.HOST, config.PORT, None))
        thread_http.start()

        # HTTPS certifikát
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain("cert.pem", "key.pem")

        # Spuštění HTTPS serveru ve vlákně
        thread_https = threading.Thread(target=run_flask, args=(config, config.HOST, https_port, ssl_context))
        thread_https.start()

        # Počkej na dokončení obou vláken
        thread_http.join()
        thread_https.join()

    except KeyboardInterrupt:
        logger.info("Server byl ukončen")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Nastala chyba při běhu serveru: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
