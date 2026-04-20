# 这里导入时间工具，用来记录创建时间和到期时间。
from datetime import datetime

# 这里导入可选类型，表示某些字段可以为空。
from typing import Optional

# 这里导入 SQLModel 相关对象，用来定义数据库表。
from sqlmodel import Field, SQLModel


# 这里定义用户表，用来存放购买套餐的人。
class User(SQLModel, table=True):
    # 这里定义用户主键，自增整数。
    id: Optional[int] = Field(default=None, primary_key=True)

    # 这里定义邮箱，后续可以拿它做登录账号。
    email: str = Field(index=True, unique=True)

    # 这里定义昵称或内部备注名。
    name: str

    # 这里记录用户创建时间。
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 这里记录用户套餐到期时间。
    expires_at: datetime

    # 这里记录用户是否可用，后面可用于封禁。
    is_active: bool = Field(default=True)


# 这里定义设备表，每个设备对应一个 WireGuard peer。
class Device(SQLModel, table=True):
    # 这里定义设备主键，自增整数。
    id: Optional[int] = Field(default=None, primary_key=True)

    # 这里记录这个设备属于哪个用户。
    user_id: int = Field(index=True, foreign_key="user.id")

    # 这里记录设备名字，比如 iphone_1 或 windows_laptop。
    device_name: str

    # 这里保存客户端私钥，最小版先明文存，生产版要改成加密存储。
    private_key: str

    # 这里保存客户端公钥，后面服务端写 peer 时会用到。
    public_key: str = Field(index=True, unique=True)

    # 这里保存这个设备分配到的隧道 IP。
    assigned_ip: str = Field(index=True, unique=True)

    # 这里保存完整客户端配置文本，方便用户一键下载。
    client_config: str

    # 这里表示这个设备当前是否启用。
    is_enabled: bool = Field(default=True)

    # 这里记录设备创建时间。
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 这里记录最后一次配置变更时间。
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# 这里定义操作日志表，用来记录后台做过的重要动作。
class ActionLog(SQLModel, table=True):  # 这里定义操作日志数据库表。
    # 这里是日志主键 id。
    id: int | None = Field(default=None, primary_key=True)  # 这里保存日志 id。

    # 这里是日志创建时间。
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)  # 这里默认写入当前 UTC 时间。

    # 这里是动作类型，比如 create_user、disable_device。
    action: str = Field(index=True)  # 这里保存动作名称。

    # 这里是关联的用户 id，没有就留空。
    user_id: int | None = Field(default=None, index=True)  # 这里保存用户 id。

    # 这里是关联的设备 id，没有就留空。
    device_id: int | None = Field(default=None, index=True)  # 这里保存设备 id。

    # 这里是简单说明文字。
    message: str = Field(default="")  # 这里保存日志说明。

