# WireGuard SaaS MVP

这是一个最小可运行版本。

它能做三件事：
1. 创建用户。
2. 给用户创建设备。
3. 生成客户端 WireGuard 配置，并且可选地把 peer 写进服务器的 `wg0`。

## 这版为什么这样做

这版优先把“能开通”跑通，不先做支付、前端、工单、分销。

## 官方依据

- WireGuard 官方安装页列出了 Windows、iOS、Android、Ubuntu 等平台支持，并给出 Ubuntu 上 `apt install wireguard` 的方式。  
- WireGuard 官方 quick start 说明了 `wg genkey`、`wg pubkey`、`wg set`、`wg-quick` 的基本用法。  
- WireGuard 官方 limitation 页面明确说它不以混淆为目标，也不支持 TCP-over-TCP 这种路线。  

## 目录

- `app/`：后端主程序。
- `scripts/`：示例脚本。
- `.env.example`：环境变量模板。

## 先装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Linux 服务器先装 WireGuard

Ubuntu / Debian 上按 WireGuard 官方安装页，直接：

```bash
sudo apt install wireguard
```

## 先准备服务端密钥

按 WireGuard 官方 quick start：

```bash
umask 077
wg genkey | tee server_private.key | wg pubkey > server_public.key
cat server_public.key
```

## 服务端示例 `/etc/wireguard/wg0.conf`

```ini
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = 在这里填 server_private.key 的内容
SaveConfig = true
```

然后启用：

```bash
sudo wg-quick up wg0
sudo wg show
```

## 配置环境变量

```bash
cp .env.example .env
```

然后把 `.env` 里这几个值改掉：

- `WG_SERVER_ENDPOINT`
- `WG_SERVER_PUBLIC_KEY`
- `WG_APPLY_CHANGES`

## 启动 API

```bash
fastapi dev app/main.py
```

## 先建用户

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "first_user",
    "days": 30
  }'
```

## 再建设备

把上一步返回的 `id` 换进去：

```bash
curl -X POST http://127.0.0.1:8000/devices \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "device_name": "iphone_1"
  }'
```

返回结果里会直接带：

- 客户端私钥
- 客户端公钥
- 分配到的隧道 IP
- 完整客户端配置文本

## 禁用设备

```bash
curl -X POST http://127.0.0.1:8000/devices/1/disable
```

## 当前最重要的限制

1. 这版为了最小可运行，API 里直接调用了系统 `wg` 命令。
2. 真正商用时，不建议让 Web 进程直接拿高权限。
3. 下一版应改成“API + Provisioner”分离，Provisioner 用受限 sudo 或 systemd service 执行。
4. 这版数据库先用 SQLite，只为先跑通；真卖钱时换 PostgreSQL。
