"""Entry point for the Docker-free Windows desktop build (PyInstaller
--onefile). Not used by the Docker image, which keeps running
`alembic upgrade head && uvicorn app.main:app` from its CMD instead.

Responsibilities this script has that the Docker CMD doesn't need:
- Resolve two different base directories. PyInstaller's --onefile mode
  unpacks bundled read-only files (this app's code, alembic/) into a
  temp dir (sys._MEIPASS) on every launch; anything that must persist
  between runs (.env, the SQLite database, novel_storage/) instead
  belongs next to the installed .exe (sys.executable's directory).
- chdir into that persistent directory before importing app.config, so
  its relative '.env' / novel_storage_dir / SQLite file paths resolve
  there rather than into the temp extraction dir.
- Run Alembic migrations in-process (no separate `alembic` command is on
  PATH in a frozen build) before starting the server.
"""
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)  # noqa: SLF001 (PyInstaller's own attribute)
    APP_DIR = Path(sys.executable).parent
else:
    BUNDLE_DIR = Path(__file__).parent
    APP_DIR = BUNDLE_DIR

os.chdir(APP_DIR)


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BUNDLE_DIR / 'alembic.ini'))
    cfg.set_main_option('script_location', str(BUNDLE_DIR / 'alembic'))
    command.upgrade(cfg, 'head')


def main() -> None:
    run_migrations()
    import uvicorn
    from app.main import app

    uvicorn.run(app, host='127.0.0.1', port=8000)


if __name__ == '__main__':
    main()
