import argparse
import os
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


def run_web(args):
    print("Starting server")
    print(f"Open http://localhost:{args.port} in your browser")

    os.environ["ULTRA_TRACE_DATA"] = os.path.abspath(args.data_path)

    if not args.no_browser:
        webbrowser.open(f"http://localhost:{args.port}")

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "web":
        run_web(args)


if __name__ == "__main__":
    main()
