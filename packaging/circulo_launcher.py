"""Punto de entrada del ejecutable portable de Círculo (PyInstaller)."""
import os
import sys


def configure_bundled_browser():
    """Indica a Playwright que use el Chromium incluido dentro del paquete en lugar de una descarga externa."""
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')


def main():
    configure_bundled_browser()
    if '--run-scheduled' in sys.argv[1:]:
        from runner.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[1:]))
    from runner.server import main as server_main
    server_main()


if __name__ == '__main__':
    main()
