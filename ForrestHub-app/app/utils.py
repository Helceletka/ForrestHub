import socket
import logging
import os
from datetime import datetime



def get_local_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    s.close()
    return ip_address


def is_port_free(ip: str, port: int) -> bool:
    """Check if port is free on given IP address."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)  # Timeout pro rychlejší odpověď
        return s.connect_ex((ip, port)) != 0


def find_free_port(ip: str, port: int) -> int:
    """Find free port on given IP address."""
    while not is_port_free(ip, port):
        port += 1
    return port

def get_readable_ip(host: str, port: int, host_qr: str | None) -> str:
    if host_qr:
        return host_qr
    return host + (f":{port}" if port not in [80, 443] else "")


def setup_logging(root_dir: str, log_folder: str = "ForrestHubLogs"):
    logs_dir = os.path.join(root_dir, log_folder)
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(
        logs_dir, f'ForrestHub_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    )
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)

    return logging.getLogger(__name__)
