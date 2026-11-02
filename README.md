# weron-signaler-python

纯 Python WebSocket relay 服务器，用于 weron VPN 信令。

## 与 Cloudflare Workers 版的关系

Cloudflare Workers 版（`/root/github/weron-signaler-cf/`）使用 Durable Objects，
只能在 Cloudflare 平台上运行。本项目把它移植为纯 Python + aiohttp，
可在任何 Linux 服务器上直接运行，单端口同时提供 HTTP 和 WebSocket 服务。

## 功能

- WebSocket 信令中继：客户端 A ↔ 客户端 B，服务器只做广播
- BINARY 帧原样转发：Go 客户端发送的 AES-GCM 加密数据以 BinaryMessage 发送，
  服务端收到后原样广播，保证对端拿到原始字节
- 客户端上限（默认 256）
- 优雅关闭（SIGINT / SIGTERM）

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

## 安装

```bash
pip install -r requirements.txt
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORT` | `8788` | 监听端口 |
| `HOST` | `0.0.0.0` | 监听地址 |

## 运行

```bash
python3 relay.py
```

自定义端口和 IP：

```bash
PORT=9090 HOST=192.168.1.100 python3 relay.py
```

## 三个实现的对比

| | Python 版 | Node.js 版 | C 版（libwebsockets） |
|---|---|---|---|
| 运行时 | Python >= 3.10 | Node.js >= 16 | 零依赖（静态二进制） |
| 部署 | `pip install` | `npm install` | 直接运行二进制 |
| 内存 | ~15MB | ~30MB | ~2MB |
| 并发 | asyncio 单线程 | 事件循环 | libwebsockets 多线程 |
| TLS | 需反向代理 | 需反向代理 | 编译时可选 OpenSSL |

## 注意事项

Go 客户端**必须**使用 `BinaryMessage` 发送 AES-GCM 加密数据。
TextMessage 会因 UTF-8 强制约束导致二进制数据损坏，无法在 relay 端修复。