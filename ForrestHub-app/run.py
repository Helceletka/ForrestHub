import logging
import sys
import webbrowser
import click
from app.init import create_app, socketio
from config import Config
from pathlib import Path
from app.utils import is_port_free, find_free_port, setup_logging
from werkzeug.middleware.proxy_fix import ProxyFix
from app.utils import get_readable_ip

logger = logging.getLogger(__name__)
__version__ = (Path(__file__).parent / "VERSION").read_text().strip()


def run_flask(config: object | str, host="0.0.0.0", port=4444):
    app = create_app(config)

    # Za reverzní proxy – respektuj X-Forwarded-* (host, proto, port, prefix)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1, x_prefix=1)

    # Preferuj https pro generované URL a zabezpeč cookies
    app.config.update(
        PREFERRED_URL_SCHEME="https",
        SESSION_COOKIE_SECURE=True,
        REMEMBER_COOKIE_SECURE=True,
    )

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
        config.PORT = port

    if host:
        config.HOST = host
        
    if host_qr:
        config.HOST_QR = host_qr
        config.HOST_QR_READABLE = get_readable_ip(config.HOST, config.PORT, config.HOST_QR)

    if not is_port_free(config.HOST, config.PORT):
        new_port = find_free_port(config.HOST, 4444)
        logger.warning(f"Port {config.PORT} je již používán, přepínám na další dostupný port: {new_port}")
        config.PORT = new_port

    local_ip = f"http://{config.HOST}:{config.PORT}"

    try:
        if config.FROZEN:
            webbrowser.open(local_ip)
            webbrowser.open(f"{local_ip}/admin")

        logger.info(f"Server byl spuštěn na adrese: {local_ip}")
        logger.info("Press Ctrl-C to stop the server")

        run_flask(config=config, host=config.HOST, port=config.PORT)
    except KeyboardInterrupt:
        logger.info("Server byl ukončen")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Nastala chyba při běhu serveru: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
