# 服务器最小开局步骤

> 先说明：下面是演示版最小步骤，用来先跑通。

## 1）安装 WireGuard

```bash
sudo apt update
sudo apt install wireguard
```

## 2）生成服务端密钥

```bash
umask 077
wg genkey | tee server_private.key | wg pubkey > server_public.key
cat server_public.key
```

## 3）写服务端配置

```ini
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = 把 server_private.key 的内容粘进来
SaveConfig = true
```

## 4）启动 wg0

```bash
sudo wg-quick up wg0
sudo wg show
```

## 5）跑 API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
fastapi dev app/main.py
```
