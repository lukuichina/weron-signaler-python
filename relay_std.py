#!/usr/bin/env python3
"""weron-signaler-python — zero-dependency pure Python WebSocket relay.

No pip install required — uses only the Python 3.11+ standard library.

Usage:
    python3 relay_std.py
    python3 relay_std.py -i 0.0.0.0 -p 8788
    PORT=8788 HOST=0.0.0.0 python3 relay_std.py

CLI arguments take precedence over environment variables.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import signal
import sys
import struct

log = logging.getLogger("relay0")

clients: set = set()

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _parse_args():
    parser = argparse.ArgumentParser(
        description="weron-signaler-python — zero-dependency WebSocket relay"
    )
    parser.add_argument("-i", default=None, help="Listen address (env: HOST)")
    parser.add_argument("-p", type=int, default=None, help="Listen port (env: PORT)")
    parser.add_argument("-V", "--version", action="store_true", help="Print version")
    return parser.parse_args()


_args = _parse_args()

if _args.version:
    print("weron-signaler-python 0.1.0")
    sys.exit(0)

HOST = _args.i if _args.i is not None else os.environ.get("HOST", "0.0.0.0")
PORT = _args.p if _args.p is not None else int(os.environ.get("PORT", "8788"))


def _encode_frame(payload: bytes, opcode: int = 0x2) -> bytes:
    """Encode a WebSocket server→client frame (unmasked)."""
    header = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header += bytes([length])
    elif length < 65536:
        header += bytes([126]) + struct.pack(">H", length)
    else:
        header += bytes([127]) + struct.pack(">Q", length)
    return header + payload


def ws_upgrade_handler(request_data: bytes):
    """Parse WebSocket upgrade request, return 101 response bytes or None."""
    try:
        lines = request_data.decode("utf-8", errors="replace").split("\r\n")
    except Exception:
        return None

    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    key = headers.get("sec-websocket-key", "")
    if not key:
        return None

    accept = base64.b64encode(
        hashlib.sha1((key + GUID).encode()).digest()
    ).decode()

    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    ).encode()


async def ws_client(reader, writer):
    """Handle a single WebSocket client connection."""
    addr = writer.get_extra_info("peername")
    try:
        data = await reader.readuntil(b"\r\n\r\n")
        resp = ws_upgrade_handler(data)
        if resp is None:
            writer.close()
            return

        writer.write(resp)
        await writer.drain()

        clients.add(writer)
        log.info("client connected %s, total=%d", addr, len(clients))

        async def broadcast(payload: bytes):
            dead = []
            for peer in list(clients):
                if peer is writer:
                    continue
                try:
                    peer.write(_encode_frame(payload))
                    await peer.drain()
                except Exception:
                    dead.append(peer)
            for d in dead:
                clients.discard(d)
                try:
                    d.close()
                except Exception:
                    pass

        # Buffer for fragmented messages
        frag_buf = bytearray()

        while True:
            header = await reader.readexactly(2)

            fin = header[0] & 0x80
            opcode = header[0] & 0x0F
            masked = header[1] & 0x80
            length = header[1] & 0x7F

            if length == 126:
                length = int.from_bytes(await reader.readexactly(2), "big")
            elif length == 127:
                length = int.from_bytes(await reader.readexactly(8), "big")

            mask_key = await reader.readexactly(4) if masked else None
            payload = await reader.readexactly(length)

            if mask_key:
                payload = bytes(
                    b ^ mask_key[i % 4] for i, b in enumerate(payload)
                )

            if opcode == 0x8:  # close
                # Echo close frame back
                try:
                    writer.write(_encode_frame(payload, opcode=0x8))
                    await writer.drain()
                except Exception:
                    pass
                break

            if opcode == 0x9:  # ping → pong
                writer.write(_encode_frame(payload, opcode=0xA))
                await writer.drain()
                continue

            if opcode == 0xA:  # pong
                continue

            # Data frames: 0x0=continuation, 0x1=text, 0x2=binary
            if opcode == 0x0:
                frag_buf.extend(payload)
                if fin:
                    await broadcast(bytes(frag_buf))
                    frag_buf.clear()
            elif opcode in (0x1, 0x2):
                if fin:
                    await broadcast(payload)
                else:
                    frag_buf.clear()
                    frag_buf.extend(payload)

    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        log.debug("client error %s: %s", addr, e)
    finally:
        clients.discard(writer)
        try:
            writer.close()
        except Exception:
            pass
        log.info("client disconnected %s, total=%d", addr, len(clients))


async def main():
    log.info("weron-signaler-python starting on %s:%d", HOST, PORT)

    server = await asyncio.start_server(
        ws_client, HOST, PORT
    )
    log.info("listening on %s:%d", HOST, PORT)

    async with server:
        await server.serve_forever()


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