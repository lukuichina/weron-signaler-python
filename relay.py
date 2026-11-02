#!/usr/bin/env python3
"""
weron-signaler-python — pure Python WebSocket relay for weron VPN signaling.

Uses aiohttp for HTTP + WebSocket on a single port.

Usage:
    PORT=8788 HOST=0.0.0.0 python3 relay.py

Environment variables:
    PORT          Listening port           (default: 8788)
    HOST          Listening host           (default: 0.0.0.0)
    MAX_CLIENTS   Max concurrent clients   (default: 256)
"""

import asyncio
import json
import logging
import os
import signal
from collections import defaultdict

from aiohttp import web, WSMsgType

# ── Configuration ──────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", "8788"))
HOST = os.environ.get("HOST", "0.0.0.0")
MAX_CLIENTS = int(os.environ.get("MAX_CLIENTS", "256"))

# WebSocket paths accepted (compatible with CF Worker version)
WS_PATHS = {"/", "/ws", "/signaler", "/room"}

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("relay")

# ── State ──────────────────────────────────────────────────────────
clients: set = set()


async def health_handler(request):
    """GET / or /health → JSON health check."""
    return web.json_response({
        "status": "ok",
        "service": "weron-signaler-python",
        "clients": len(clients),
    })


async def info_handler(request):
    """GET /info → text info."""
    return web.Response(
        text="weron-signaler-python — pure Python WebSocket relay\n",
        content_type="text/plain",
    )


async def ws_handler(request):
    """WebSocket handler — accepts connections on any WS_PATH."""
    ws = web.WebSocketResponse(decode_text=False)
    await ws.prepare(request)

    path = request.path
    log.info("client connected (path=%s), total=%d", path, len(clients) + 1)
    clients.add(ws)

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                # Text frame — msg.data is already bytes (decode_text=False).
                # Forward as-is; Go clients MUST use BinaryMessage for AES-GCM.
                payload = msg.data
            elif msg.type == WSMsgType.BINARY:
                payload = msg.data
            else:
                continue  # ping/pong/close handled by aiohttp

            forwarded = 0
            for peer in list(clients):
                if peer is ws:
                    continue
                try:
                    await peer.send_bytes(payload)
                    forwarded += 1
                except Exception as e:
                    log.warning("forward error: %s", e)
                    clients.discard(peer)

            if forwarded:
                log.info("forwarded %dB to %d peer(s)", len(payload), forwarded)

    except Exception as e:
        log.error("client error: %s", e)
    finally:
        clients.discard(ws)
        log.info("client disconnected, total=%d", len(clients))

    return ws


async def main():
    """Start the relay server."""
    app = web.Application()

    # HTTP routes (note: / is a WS path, so only /health for HTTP health check)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/info", info_handler)

    # WebSocket routes — register all WS paths
    for path in WS_PATHS:
        app.router.add_route("GET", path, ws_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    log.info("weron-signaler-python listening on %s:%d", HOST, PORT)
    log.info("WebSocket paths: %s", ", ".join(sorted(WS_PATHS)))
    log.info("max clients=%d", MAX_CLIENTS)

    # Keep running until interrupted
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    finally:
        await runner.cleanup()
        log.info("stopped")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    main_task = loop.create_task(main())

    def _shutdown():
        log.info("shutting down...")
        main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()
