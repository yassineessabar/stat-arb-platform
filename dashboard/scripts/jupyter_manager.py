#!/usr/bin/env python3
import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    start_parser = subparsers.add_parser('start')
    start_parser.add_argument('--port', type=int, default=8888)
    start_parser.add_argument('--notebook-dir', type=str)

    args = parser.parse_args()

    # For now, return a mock success response
    result = {
        "success": True,
        "url": f"http://127.0.0.1:{args.port}/lab?token=mock-token",
        "token": "mock-token",
        "port": args.port,
        "notebook_dir": args.notebook_dir,
        "pid": 12345,
        "message": "JupyterLab server started successfully (mock mode)",
        "mode": "mock"
    }

    print(json.dumps(result))

if __name__ == '__main__':
    main()