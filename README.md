# weron-signaler-python

纯 Python WebSocket relay 服务器，用于 weron VPN 信令。

**`relay_std.py`**：零依赖，纯 Python stdlib 实现，基于
`asyncio.start_server` + `asyncio.StreamReader/Writer`，
不依赖 `aiohttp`、`websockets` 等任何第三方库。
直接 `python3 relay_std.py` 即可运行，无需 `pip install`。

**`relay_ws.py`**：使用 `websockets>=14` 库，API 更简洁，
内置 ping/pong 心跳，需 `pip install websockets>=14`。

## 与 Cloudflare Workers 版的关系

Cloudflare Workers 版（`/root/github/weron-signaler-cf/`）使用 Durable Objects，
只能在 Cloudflare 平台上运行。本项目把它移植为纯 Python stdlib，
可在任何 Linux 服务器上直接运行。

## 功能

- WebSocket 信令中继：客户端 A ↔ 客户端 B，服务器只做广播
- BINARY 帧原样转发：Go 客户端发送的 AES-GCM 加密数据以 BinaryMessage 发送，
  服务端收到后原样广播，保证对端拿到原始字节
- 手动 WebSocket frame 解析：基于 `asyncio.StreamReader/Writer`，
  不依赖任何第三方 WebSocket 库
- 客户端上限（默认 256）
- 优雅关闭（SIGINT / SIGTERM）
- CLI 参数：`-i` 监听地址、`-p` 端口、`-V` 版本、`-h` 帮助

## WebSocket 路径

以下路径均可建立 WebSocket 连接（与 CF Worker 版兼容）：

| 路径 | 说明 |
|---|---|
| `/` | 默认路径 |
| `/ws` | CF Worker 版路径 |
| `/signaler` | CF Worker 版路径（`WS_PATH` 配置） |
| `/room` | CF Worker 版路径 |

HTTP 路径：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查，返回 JSON |
| `GET` | `/info` | 服务信息 |
| 其他 | 任意 | 返回 404 |

## 变体

本目录包含三个实现：

| 文件 | 依赖 | 说明 |
|---|---|---|
| `relay.py` | `aiohttp` | HTTP + WebSocket 统一端口，环境变量配置 |
| `relay_std.py` | 零依赖（纯 stdlib） | 手动 WebSocket frame 解析，`asyncio.start_server` |
| `relay_ws.py` | `websockets>=14` | 使用 `websockets` 库，API 更简洁，内置 ping/pong 心跳 |

## 安装

### relay.py（aiohttp）

```bash
pip install aiohttp
python3 relay.py
python3 relay.py -i 0.0.0.0 -p 8788
PORT=8788 HOST=0.0.0.0 python3 relay.py
```

CLI 参数优先级高于环境变量。

### relay_std.py（零依赖）

**无需安装**。直接运行：

```bash
python3 relay_std.py
python3 relay_std.py -i 0.0.0.0 -p 8788
PORT=8788 HOST=0.0.0.0 python3 relay_std.py
```

### relay_ws.py（websockets 库）

```bash
pip install websockets>=14
python3 relay_ws.py
python3 relay_ws.py -i 0.0.0.0 -p 8788
PORT=8788 HOST=0.0.0.0 python3 relay_ws.py
```

三个版本均支持 CLI 参数和环境变量，CLI 参数优先级更高。

## CLI 参数 / 环境变量

### relay_std.py / relay_ws.py（CLI 参数）

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-i <IP>` | 监听地址 | `0.0.0.0` |
| `-p <PORT>` | 监听端口 | `8788` |
| `-V, --version` | 打印版本信息 | — |
| `-h, --help` | 打印帮助信息 | — |

### relay.py（CLI 参数 + 环境变量）

| 参数 | 说明 | 默认值 | 对应环境变量 |
|---|---|---|---|
| `-i <IP>` | 监听地址 | `0.0.0.0` | `HOST` |
| `-p <PORT>` | 监听端口 | `8788` | `PORT` |
| `-m <N>` | 最大并发客户端数 | `256` | `MAX_CLIENTS` |
| `-V, --version` | 打印版本信息 | — | — |

## 六个实现的对比

| | Python（aiohttp） | Python（stdlib） | Python（websockets） | Node.js（自托管） | C（libwebsockets） | Rust（axum） |
|---|---|---|---|---|---|---|
| 文件 | `relay.py` | `relay_std.py` | `relay_ws.py` | `weron-signaler-nodejs/app.js` | `weron-signaler-c/` | `weron-signaler-rust/` |
| 运行时 | Python + aiohttp | Python >= 3.10 stdlib | Python + websockets | Node.js >= 16 + `ws` | 零依赖（静态二进制） | Rust std + tokio |
| 部署 | `pip install aiohttp` | 直接运行脚本 | `pip install websockets` | `npm install && npm start` | 直接运行二进制 | `cargo build --release` |
| 内存 | ~15MB | ~5MB | ~8MB | ~30MB | ~2MB | ~5MB |
| 并发 | asyncio 单线程 | asyncio 单线程 | asyncio 单线程 | 单线程事件循环 | libwebsockets 多线程 | tokio 异步多线程 |
| TLS | 需反向代理 | 需反向代理 | 需反向代理 | 需反向代理 | 编译时可选 OpenSSL | 需反向代理 |
| 分片重组 | 不支持 | 不支持 | 不支持 | 不支持 | ✅ 原生支持 | 不支持 |
| 第三方依赖 | `aiohttp` | 零 | `websockets>=14` | `ws` | 零 | tokio + axum + tungstenite |

### Node.js 版（自托管）

位于 `/root/github/weron-signaler-nodejs/`，两个变体：
- `app.js`：使用 `ws` 库，需 `npm install`
- `app_std.js`：零依赖纯 Node.js stdlib，`node app_std.js` 直接运行

纯自托管方案，不依赖 Cloudflare 平台。

### Cloudflare Workers 版

位于 `/root/github/weron-signaler-cf/`，
运行在 Cloudflare 平台上，使用 Durable Objects 管理房间状态。
通过 `wrangler deploy` 部署，底层为 Node.js 兼容模式。
源码入口：`src/worker.js`。

## 注意事项

Go 客户端**必须**使用 `BinaryMessage` 接收数据。
TextMessage 在 relay 端会以 BINARY 帧转发——
如果原始字节不是合法 UTF-8，TextMessage 本身在客户端就会编码失败。