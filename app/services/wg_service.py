# 这里导入标准库中的 IP 地址处理工具，用来安全地分配内网地址。
import ipaddress  # 这里导入 IP 网段处理工具，后面要用它遍历 10.0.0.0/24 这样的网段。

# 这里导入子进程模块，用来调用系统里的 wg 命令。
import subprocess  # 这里导入子进程工具，后面要执行 wg genkey、wg pubkey、wg set、wg show。

# 这里导入时间工具，用来更新修改时间。
from datetime import datetime  # 这里导入当前时间工具，后面写数据库更新时间要用。

# 这里导入会话对象和查询函数，用来读写数据库。
from sqlmodel import Session, select  # 这里导入数据库会话和查询工具。

# 这里导入我们自己的配置。
from app.config import settings  # 这里导入 .env 里的配置。

# 这里导入设备模型，后面会写入数据库。
from app.models import Device  # 这里导入设备表模型。


# 这里定义一个运行系统命令的小工具函数。
def run_command(command: list[str]) -> str:
    # 这里先尝试执行命令。
    try:
        # 这里执行系统命令，要求失败时直接抛异常，并把标准输出和错误输出都抓回来。
        result = subprocess.run(command, check=True, capture_output=True, text=True)

    # 这里专门捕获“命令执行失败”的异常。
    except subprocess.CalledProcessError as e:
        # 这里把标准输出整理成字符串，防止是空值。
        stdout_text = (e.stdout or "").strip()

        # 这里把错误输出整理成字符串，防止是空值。
        stderr_text = (e.stderr or "").strip()

        # 这里把原始命令拼成人能看懂的一行文本。
        command_text = " ".join(command)

        # 这里抛出一个更容易读懂的新错误，后面 FastAPI 日志会更清楚。
        raise RuntimeError(
            f"系统命令执行失败: {command_text} | stdout={stdout_text} | stderr={stderr_text}"
        ) from e

    # 这里返回去掉前后空白后的标准输出内容。
    return result.stdout.strip()


# 这里定义生成一对 WireGuard 密钥的函数。
def generate_key_pair() -> tuple[str, str]:
    # 这里调用 wg genkey 生成客户端私钥。
    private_key = run_command(["wg", "genkey"])

    # 这里把私钥送给 wg pubkey，换算出对应的公钥。
    public_key = subprocess.run(
        ["wg", "pubkey"],  # 这里调用 wg pubkey 命令。
        input=private_key,  # 这里把刚生成的私钥喂给命令。
        check=True,  # 这里要求失败时抛异常。
        capture_output=True,  # 这里抓取输出内容。
        text=True,  # 这里按文本模式处理输入输出。
    ).stdout.strip()  # 这里取出标准输出并去掉换行。

    # 这里把私钥和公钥一起返回。
    return private_key, public_key


# 这里定义一个函数，用来读取当前系统 WireGuard 接口里已经占用的 IP。
def get_live_used_ips() -> set[str]:
    # 这里先准备一个空集合，后面把系统中已占用的 IP 放进去。
    used_ips: set[str] = set()

    # 这里读取当前接口里的 allowed-ips 信息。
    output = run_command(["wg", "show", settings.WG_INTERFACE, "allowed-ips"])

    # 这里如果系统里暂时没有任何 peer，输出可能是空字符串，直接返回空集合。
    if not output:
        # 这里直接返回空集合。
        return used_ips

    # 这里按行处理 wg show 的输出。
    for line in output.splitlines():
        # 这里先去掉每行前后的空白字符。
        line = line.strip()

        # 这里如果某一行是空的，就跳过。
        if not line:
            # 这里继续处理下一行。
            continue

        # 这里按空白分割一行，通常会得到“公钥 + allowed-ips”两部分。
        parts = line.split()

        # 这里如果格式不完整，就跳过，避免程序崩掉。
        if len(parts) < 2:
            # 这里继续处理下一行。
            continue

        # 这里取第二部分，也就是 allowed-ips 文本，例如 10.0.0.2/32。
        allowed_ips_text = parts[1]

        # 这里按逗号继续拆分，兼容一个 peer 有多个网段的情况。
        for item in allowed_ips_text.split(","):
            # 这里先去掉每个网段前后的空白。
            item = item.strip()

            # 这里如果拆出来是空字符串，就跳过。
            if not item:
                # 这里继续处理下一个网段。
                continue

            # 这里把 /32 这种掩码去掉，只保留纯 IP 地址。
            ip_text = item.split("/")[0]

            # 这里把这个已占用 IP 放进集合里。
            used_ips.add(ip_text)

    # 这里把系统里已占用的全部 IP 返回出去。
    return used_ips


# 这里定义一个函数，用来在网段里找到下一个可用 IP。
def allocate_next_ip(session: Session) -> str:
    # 这里把配置中的 CIDR 网段解析成可操作对象。
    network = ipaddress.ip_network(settings.WG_NETWORK_CIDR)

    # 这里把数据库里已经使用过的 IP 全部取出来。
    db_used_ips = set(session.exec(select(Device.assigned_ip)).all())

    # 这里把系统 WireGuard 接口里已经存在的 IP 也读出来。
    live_used_ips = get_live_used_ips()

    # 这里把数据库和系统里的已占用 IP 合并到一起。
    used_ips = db_used_ips | live_used_ips

    # 这里遍历网段中的所有主机地址。
    for host in network.hosts():
        # 这里把主机地址转成字符串，方便比较和存库。
        host_ip = str(host)

        # 这里跳过服务端自己占用的地址，例如 10.0.0.1。
        if host_ip == settings.WG_SERVER_TUN_IP.split("/")[0]:
            # 这里继续检查下一个地址。
            continue

        # 这里如果该地址还没被数据库或系统占用，就把它返回出去。
        if host_ip not in used_ips:
            # 这里返回这个可用地址。
            return host_ip

    # 这里如果整个网段都没有可用地址了，就抛出错误。
    raise ValueError("没有可用的隧道 IP 了，请更换更大的网段。")


# 这里定义一个函数，用来生成客户端配置文本。
def build_client_config(private_key: str, assigned_ip: str) -> str:
    # 这里把配置内容拼成标准 WireGuard 客户端配置。
    return "\n".join([
        "[Interface]",  # 这里是客户端配置的接口段开头。
        f"PrivateKey = {private_key}",  # 这里写客户端自己的私钥。
        f"Address = {assigned_ip}/32",  # 这里写客户端分配到的隧道 IP。
        f"DNS = {settings.WG_DNS}",  # 这里写客户端连上后使用的 DNS。
        "",  # 这里插一个空行，让配置更清楚。
        "[Peer]",  # 这里是对端服务端配置段开头。
        f"PublicKey = {settings.WG_SERVER_PUBLIC_KEY}",  # 这里写服务端公钥。
        f"AllowedIPs = {settings.WG_ALLOWED_IPS}",  # 这里写客户端默认路由规则。
        f"Endpoint = {settings.WG_SERVER_ENDPOINT}",  # 这里写服务端公网入口地址。
        f"PersistentKeepalive = {settings.WG_PERSISTENT_KEEPALIVE}",  # 这里写保活秒数。
    ])


# 这里定义一个函数，用来把 peer 真正写进服务器上的 wg 接口。
def apply_peer_to_server(public_key: str, assigned_ip: str) -> None:
    # 这里如果配置要求只做演示不真写系统，就直接返回。
    if not settings.WG_APPLY_CHANGES:
        # 这里直接结束函数，不做真实写入。
        return

    # 这里调用 wg set，把 peer 加进指定接口。
    run_command([
        "wg",  # 这里调用 wg 命令。
        "set",  # 这里表示要修改接口配置。
        settings.WG_INTERFACE,  # 这里写要修改的接口名，比如 wg0。
        "peer",  # 这里表示后面跟的是 peer 信息。
        public_key,  # 这里写新设备的公钥。
        "allowed-ips",  # 这里表示后面要设置 allowed-ips。
        f"{assigned_ip}/32",  # 这里给这台设备分配一个唯一的 /32 地址。
    ])


# 这里定义一个函数，用来从服务端删除 peer。
def remove_peer_from_server(public_key: str) -> None:
    # 这里如果配置要求不真正改系统，就直接返回。
    if not settings.WG_APPLY_CHANGES:
        # 这里直接结束函数。
        return

    # 这里调用 wg set peer remove，把这个设备从服务端配置中移除。
    run_command([
        "wg",  # 这里调用 wg 命令。
        "set",  # 这里表示要修改接口配置。
        settings.WG_INTERFACE,  # 这里写接口名。
        "peer",  # 这里表示后面跟的是 peer。
        public_key,  # 这里写要删除的 peer 公钥。
        "remove",  # 这里表示删除这个 peer。
    ])


# 这里定义一个核心函数，用来创建设备并生成配置。
def create_device(session: Session, user_id: int, device_name: str) -> Device:
    # 这里先生成这一台设备自己的密钥对。
    private_key, public_key = generate_key_pair()

    # 这里给这台设备分配一个新的隧道 IP。
    assigned_ip = allocate_next_ip(session)

    # 这里根据密钥和 IP 生成客户端配置文本。
    client_config = build_client_config(private_key=private_key, assigned_ip=assigned_ip)

    # 这里把 peer 写进服务器的 wg0。
    apply_peer_to_server(public_key=public_key, assigned_ip=assigned_ip)

    # 这里创建数据库中的设备对象。
    device = Device(
        user_id=user_id,  # 这里写所属用户 ID。
        device_name=device_name,  # 这里写设备名字。
        private_key=private_key,  # 这里保存客户端私钥。
        public_key=public_key,  # 这里保存客户端公钥。
        assigned_ip=assigned_ip,  # 这里保存分配到的隧道 IP。
        client_config=client_config,  # 这里保存完整客户端配置。
        is_enabled=True,  # 这里默认设备是启用状态。
        updated_at=datetime.utcnow(),  # 这里写当前更新时间。
    )

    # 这里把新设备加入数据库会话。
    session.add(device)

    # 这里提交事务，让数据真正写入数据库。
    session.commit()

    # 这里刷新对象，拿到数据库最新值，比如 id。
    session.refresh(device)

    # 这里把创建好的设备对象返回出去。
    return device


# 这里定义一个函数，用来禁用某台设备。
def disable_device(session: Session, device: Device) -> Device:
    # 这里先从服务器接口中删除这个 peer。
    remove_peer_from_server(public_key=device.public_key)

    # 这里把数据库状态改成禁用。
    device.is_enabled = False

    # 这里更新时间，方便后续审计。
    device.updated_at = datetime.utcnow()

    # 这里把修改后的设备重新放回会话。
    session.add(device)

    # 这里提交事务。
    session.commit()

    # 这里刷新对象，确保拿到数据库中的最新值。
    session.refresh(device)

    # 这里把禁用后的设备返回出去。
    return device


def restore_device(session, device):
    from app.config import settings
    import subprocess

    if settings.WG_APPLY_CHANGES:
        subprocess.run(
            [
                "wg",
                "set",
                settings.WG_INTERFACE,
                "peer",
                device.public_key,
                "allowed-ips",
                f"{device.assigned_ip}/32",
            ],
            check=True,
        )

    device.is_enabled = True
    session.add(device)
    session.commit()
    session.refresh(device)
    return device