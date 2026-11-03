#!/usr/bin/env python3
"""weron-signaler-python — WebSocket relay using the `websockets` library.

Requires: pip install websockets>=14

Usage:
    python3 relay_ws.py
    python3 relay_ws.py -i 0.0.0.0 -p 8788
    PORT=8788 HOST=0.0.0.0 python3 relay_ws.py

CLI arguments take precedence over environment variables.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys

import websockets
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from websockets import Response, Headers

log = logging.getLogger("relay_ws")

# Set of active WebSocket connections
clients: set = set()

# WebSocket subprotocol / path configuration
WS_PATHS = ("/", "/ws", "/signaler", "/room")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="weron-signaler-python (websockets lib) — WebSocket relay"
    )
    parser.add_argument("-i", default=None, help="Listen address (env: HOST)")
    parser.add_argument("-p", type=int, default=None, help="Listen port (env: PORT)")
    parser.add_argument("-V", "--version", action="store_true", help="Print version")
    return parser.parse_args()


_args = _parse_args()

if _args.version:
    print("weron-signaler-python-ws 0.1.0")
    sys.exit(0)

HOST = _args.i if _args.i is not None else os.environ.get("HOST", "0.0.0.0")
PORT = _args.p if _args.p is not None else int(os.environ.get("PORT", "8788"))


async def handler(websocket):
    """Handle a single WebSocket client connection."""
    addr = websocket.remote_address
    clients.add(websocket)
    log.info("client connected %s, total=%d", addr, len(clients))

    try:
        async for message in websocket:
            # `message` is bytes for BinaryMessage, str for TextMessage.
            # Always treat as bytes for broadcast.
            if isinstance(message, str):
                payload = message.encode("utf-8")
            else:
                payload = message

            dead = []
            for peer in list(clients):
                if peer is websocket:
                    continue
                try:
                    await peer.send(payload)
                except Exception:
                    dead.append(peer)
            for d in dead:
                clients.discard(d)

    except ConnectionClosed:
        log.debug("client %s closed normally", addr)
    except Exception as e:
        log.warning("client %s error: %s", addr, e)
    finally:
        clients.discard(websocket)
        log.info("client disconnected %s, total=%d", addr, len(clients))


async def process_request(connection, request):
    """Reject non-WebSocket HTTP requests except /health."""
    # websockets 15.x: Request.path includes the query string.
    # Strip query before comparing against WS_PATHS.
    path = request.path.split("?", 1)[0]
    if path in WS_PATHS or path == "/health":
        return None  # allow
    return Response(404, "Not Found", headers=Headers())


async def main():
    log.info("weron-signaler-python-ws starting on %s:%d", HOST, PORT)

    async with serve(
        handler,
        HOST,
        PORT,
        process_request=process_request,
        ping_interval=20,
        ping_timeout=10,
    ):
        log.info("listening on %s:%d", HOST, PORT)
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass