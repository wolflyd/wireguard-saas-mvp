from datetime import datetime, timedelta
from sqlmodel import SQLModel


def build_expire_time(days: int) -> datetime:
    return datetime.utcnow() + timedelta(days=days)


class UserCreate(SQLModel):
    email: str
    name: str
    days: int


class UserRead(SQLModel):
    id: int
    email: str
    name: str
    expires_at: datetime
    is_active: bool


class ExtendDaysRequest(SQLModel):
    days: int


class DeviceCreate(SQLModel):
    user_id: int
    device_name: str


class DeviceSummary(SQLModel):
    id: int
    user_id: int
    device_name: str
    public_key: str
    assigned_ip: str
    is_enabled: bool


class DeviceProvisioned(DeviceSummary):
    client_config: str


class DeviceDisabled(DeviceSummary):
    pass


# 这里定义返回给前端的操作日志结构。
class ActionLogRead(SQLModel):  # 这里定义日志响应模型。
    # 这里是日志 id。
    id: int  # 这里保存日志 id。

    # 这里是日志创建时间。
    created_at: datetime  # 这里保存日志时间。

    # 这里是动作类型。
    action: str  # 这里保存动作名称。

    # 这里是用户 id。
    user_id: int | None  # 这里保存关联用户 id。

    # 这里是设备 id。
    device_id: int | None  # 这里保存关联设备 id。

    # 这里是说明文字。
    message: str  # 这里保存日志说明。

