import argparse
import os
import socket
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
        default=".",
        help="Path to the study directory (default: current directory)",
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


def _wait_for_server(host: str, port: int, timeout: float = 10.0):
    """Опрашивает порт, пока сервер не начнёт принимать соединения."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_web(args):
    print("Starting server")

    os.environ["ULTRA_TRACE_DATA"] = os.path.abspath(args.data_path)

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
