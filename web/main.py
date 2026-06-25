import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from website import create_app


def main():
    parser = argparse.ArgumentParser(description="PictureServer")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    args = parser.parse_args()

    app = create_app()
    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
