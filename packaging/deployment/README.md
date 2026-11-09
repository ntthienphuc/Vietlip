# Lip Reader deployment profiles

> Historical 1.1 deployment notes. These container and optional LLM recipes have
> not been revalidated for VietLip 1.6.0. For the current LAN application and
> selected native SO17 model, use `../windows_server/README.md`.

## 1. Windows companion server

Use the signed application APK with the Inno Setup companion server for one
workstation or a trusted LAN. The server runs one model instance and exposes a
bounded asynchronous job queue, so CPU requests are serialized without keeping
one upload request open until inference completes.

Version 1.1 also exposes `/v1/realtime` for continuous sampled-JPEG captions.
Reverse proxies must allow WebSocket upgrades. Six-second windows overlap by
one second, use latest-only backpressure and are stitched into an accumulating
transcript. Full MP4 jobs remain an independent review path for clips up to 45s.

## 2. CPU container

Prepare a model bundle directory with this layout:

```text
models/
  epoch=13-step=55986-002.ckpt
  auto_avsr/
  vocabulary/
    vi_unigram_2000.model
    vi_unigram_2000.auto_avsr_units.txt
```

Copy `lip-reader.env.example` to `lip-reader.env`, set
`LIP_MODEL_BUNDLE_DIR` in the shell, then run:

```powershell
docker compose -f compose.cpu.yaml up --build -d
```

The model bundle is mounted read-only, uploads use an in-memory temporary
filesystem, the process runs as a non-root user, and the public port binds to
localhost by default.

## 3. Internet-facing deployment

Do not publish port 7100 directly. Put an authenticated HTTPS gateway or VPN in
front of it. `Caddyfile.example` demonstrates TLS termination and the long
response timeout needed by the backward-compatible synchronous endpoint. The
mobile app should normally use `/v1/jobs`, where upload returns HTTP 202 and
the result is polled separately.

For multiple machines, replace the in-process queue with Redis/RabbitMQ and a
dedicated worker service. Keep exactly one Auto-AVSR model instance per worker
unless memory measurements prove that additional replicas fit safely.
