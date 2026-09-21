import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ultratrace",
        description="UltraTrace — ultrasound tongue imaging annotation tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    web_parser = subparsers.add_parser(
        "web", help="Start the web server and open UltraTrace in your browser"
    )
    web_parser.add_argument(
        "data_path",
        nargs="?",
        default=None,  # ← больше никакого "." по умолчанию
        help="Path to the study directory. If omitted, a folder picker will open.",
    )
    web_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=3000,
        help="Port to run the server on (default: 3000)",
    )
    web_parser.add_argument(
        "-n",
        "--no-browser",
        action="store_true",
        help="Don't open a browser automatically",
    )

    return parser


def _pick_data_directory() -> str:
    """Открывает нативный диалог выбора папки. Работает на Windows/Mac/Linux
    через tkinter, входящий в стандартную библиотеку Python."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print(
            "Error: no data directory was specified, and this Python "
            "installation doesn't include tkinter (needed for the folder "
            "picker). Please pass a path directly: ultratrace web /path/to/data",
            file=sys.stderr,
        )
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()  # прячем пустое главное окно tkinter, нужен только диалог
    root.attributes("-topmost", True)  # диалог поверх других окон

    selected = filedialog.askdirectory(
        title="Select your UltraTrace study data directory"
    )
    root.destroy()

    if not selected:
        print("No directory selected. Exiting.", file=sys.stderr)
        sys.exit(1)

    return selected


def _wait_for_server(host: str, port: int, timeout: float = 10.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_web(args):
    data_path = args.data_path or _pick_data_directory()
    data_path = os.path.abspath(data_path)

    if not os.path.isdir(data_path):
        print(f"Error: '{data_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print("Starting server")
    print(f"Using data directory: {data_path}")

    os.environ["ULTRA_TRACE_DATA"] = data_path

    host = "127.0.0.1"

    if not args.no_browser:

        def open_when_ready():
            if _wait_for_server(host, args.port):
                webbrowser.open(f"http://localhost:{args.port}")

        threading.Thread(target=open_when_ready, daemon=True).start()

    print(f"Open http://localhost:{args.port} in your browser")
    uvicorn.run("app.main:app", host=host, port=args.port)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "web":
        run_web(args)


if __name__ == "__main__":
    main()
