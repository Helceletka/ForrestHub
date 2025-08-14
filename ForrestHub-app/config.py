import os
import sys
from app.utils import get_local_ip_address
from pathlib import Path
from dotenv import load_dotenv
from pathlib import Path
from app.utils import get_readable_ip

__version__ = (Path(__file__).parent / "VERSION").read_text().strip()


load_dotenv()


class Config:
    if getattr(sys, "frozen", False):
        FROZEN = True
        PORT = os.getenv("PORT", 80)
        EXECUTABLE_DIR = Path(sys.executable).parent
        DATA_DIR = sys._MEIPASS
    else:
        FROZEN = False
        PORT = os.getenv("PORT", 4444)
        EXECUTABLE_DIR = Path(__file__).parent
        DATA_DIR = EXECUTABLE_DIR

    VERSION = __version__
    DATAFILE = "ForrestHub-data"
    LOG_FOLDER = "ForrestHub-logs"
    ALLOWED_EXTENSIONS = ["json"]
    TEMPLATES_DIR = "templates"
    GAMES_DIR = "games"
    GAMES_DIR_LIVE = "ForrestHub-games"
    ASSETS_DIR = "assets"
    PAGES_DIR = "pages"

    DEBUG = True
    USE_RELOADER = False

    # use live data if it exists
    TEMPLATES_FOLDER = Path(DATA_DIR) / TEMPLATES_DIR
    GAMES_FOLDER = Path(DATA_DIR) / GAMES_DIR
    ASSETS_FOLDER = Path(DATA_DIR) / ASSETS_DIR
    PAGES_FOLDER = Path(DATA_DIR) / PAGES_DIR
    GAMES_FOLDER_LIVE = Path(EXECUTABLE_DIR) / GAMES_DIR_LIVE

    HOST = get_local_ip_address()
    HOST_QR = os.getenv("HOST_QR")
    HOST_QR_READABLE = get_readable_ip(HOST, PORT, HOST_QR)
    TEMPLATES_AUTO_RELOAD = True

    # Disable debug and reloader when using frozen data with live data - production mode
    if not FROZEN:
        # DEBUG = False
        USE_RELOADER = True
