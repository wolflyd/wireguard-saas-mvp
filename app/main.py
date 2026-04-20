import secrets
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session, select

from app.config import settings
from app.db import get_session, init_db
from app.models import ActionLog, Device, User
from app.schemas import (
    DeviceCreate,
    DeviceDisabled,
    DeviceProvisioned,
    DeviceSummary,
    ActionLogRead,
    ExtendDaysRequest,
    UserCreate,
    UserRead,
    build_expire_time,
)
from app.services.wg_service import create_device, disable_device, restore_device
from app.services.log_service import write_action_log


app = FastAPI(title="WireGuard SaaS MVP")
security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username_ok = secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
    password_ok = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员账号或密码错误。",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@app.on_event("startup")
def on_startup() -> None:
    init_db()



@app.get("/logs", response_model=list[ActionLogRead])
def list_logs(session: Session = Depends(get_session)) -> list[ActionLog]:
    logs = session.exec(
        select(ActionLog)
        .order_by(ActionLog.created_at.desc(), ActionLog.id.desc())
        .limit(100)
    ).all()
    return list(logs)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/admin")
def admin_page(_: str = Depends(require_admin)) -> FileResponse:
    admin_html_path = Path(__file__).resolve().parent / "admin.html"
    if not admin_html_path.exists():
        raise HTTPException(status_code=404, detail="admin.html 不存在。")
    return FileResponse(admin_html_path)


@app.post("/users", response_model=UserRead)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> User:
    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="这个邮箱已经存在。")

    user = User(
        email=payload.email,
        name=payload.name,
        expires_at=build_expire_time(payload.days),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    write_action_log(session=session, action="create_user", user_id=user.id, message=f"创建用户 {user.email}")
    return user


@app.get("/users", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> list[User]:
    users = session.exec(select(User).order_by(User.id)).all()
    return list(users)





@app.post("/users/{user_id}/restore", response_model=UserRead)
def restore_user(
    user_id: int,
    session: Session = Depends(get_session),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")

    if user.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="用户已到期，请先续费。")

    user.is_active = True
    session.add(user)
    session.commit()
    session.refresh(user)
    write_action_log(session=session, action="restore_user", user_id=user.id, message=f"恢复用户 {user.email}")
    return user


@app.post("/users/{user_id}/disable", response_model=UserRead)
def disable_user(
    user_id: int,
    session: Session = Depends(get_session),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")

    enabled_devices = session.exec(
        select(Device)
        .where(Device.user_id == user.id)
        .where(Device.is_enabled == True)
    ).all()

    for device in enabled_devices:
        disable_device(session=session, device=device)

    user.is_active = False
    session.add(user)
    session.commit()
    session.refresh(user)
    write_action_log(session=session, action="disable_user", user_id=user.id, message=f"停用用户 {user.email}")
    return user


@app.post("/users/{user_id}/extend", response_model=UserRead)
def extend_user(
    user_id: int,
    payload: ExtendDaysRequest,
    session: Session = Depends(get_session),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")

    now = datetime.utcnow()
    base_time = user.expires_at if user.expires_at > now else now

    user.expires_at = base_time + timedelta(days=payload.days)
    user.is_active = True

    session.add(user)
    session.commit()
    session.refresh(user)
    write_action_log(session=session, action="extend_user", user_id=user.id, message=f"用户续费 {payload.days} 天")
    return user


@app.post("/devices", response_model=DeviceProvisioned)
def create_device_api(
    payload: DeviceCreate,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> Device:
    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已停用。")
    if user.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="用户已到期，不能继续创建设备。")

    enabled_devices = session.exec(
        select(Device)
        .where(Device.user_id == payload.user_id)
        .where(Device.is_enabled == True)
    ).all()

    if len(enabled_devices) >= settings.MAX_DEVICES_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"这个用户最多只能有 {settings.MAX_DEVICES_PER_USER} 台启用中的设备。",
        )

    device = create_device(session=session, user_id=payload.user_id, device_name=payload.device_name)
    write_action_log(session=session, action="create_device", user_id=device.user_id, device_id=device.id, message=f"创建设备 {device.device_name}")
    return device


@app.get("/devices", response_model=list[DeviceSummary])
def list_devices(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> list[Device]:
    devices = session.exec(select(Device).order_by(Device.id)).all()
    return list(devices)


@app.get("/devices/{device_id}/config", response_class=PlainTextResponse)
def get_device_config(
    device_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> str:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在。")
    return device.client_config



@app.get("/devices/{device_id}/download")
def download_device_config(
    device_id: int,
    session: Session = Depends(get_session),
) -> Response:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在。")

    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in device.device_name)
    filename = f"{safe_name or 'device'}_{device.id}.conf"

    return Response(
        content=device.client_config,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/devices/{device_id}/qr.png")
def get_device_qr_png(
    device_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> Response:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在。")

    try:
        result = subprocess.run(
            ["qrencode", "-t", "PNG", "-o", "-"],
            input=device.client_config.encode("utf-8"),
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="服务器没有安装 qrencode。")
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成二维码失败: {(e.stderr or b'').decode('utf-8', errors='ignore')}",
        )

    return Response(
        content=result.stdout,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="device_{device_id}.png"'},
    )



@app.post("/devices/{device_id}/restore", response_model=DeviceSummary)
def restore_device_api(
    device_id: int,
    session: Session = Depends(get_session),
) -> Device:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在。")

    user = session.get(User, device.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="设备所属用户不存在。")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已停用，请先恢复用户或续费。")

    if user.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="用户已到期，不能恢复设备。")

    enabled_devices = session.exec(
        select(Device)
        .where(Device.user_id == user.id)
        .where(Device.is_enabled == True)
    ).all()

    if len(enabled_devices) >= settings.MAX_DEVICES_PER_USER and not device.is_enabled:
        raise HTTPException(
            status_code=400,
            detail=f"这个用户最多只能有 {settings.MAX_DEVICES_PER_USER} 台启用中的设备。",
        )

    if device.is_enabled:
        return device

    device = restore_device(session=session, device=device)

    write_action_log(
        session=session,
        action="restore_device",
        user_id=device.user_id,
        device_id=device.id,
        message=f"恢复设备 {device.device_name}",
    )

    session.refresh(device)
    return device


@app.post("/devices/{device_id}/disable", response_model=DeviceDisabled)
def disable_device_api(
    device_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> Device:
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在。")
    if not device.is_enabled:
        write_action_log(session=session, action="disable_device", user_id=device.user_id, device_id=device.id, message=f"禁用设备 {device.device_name}")
    return device
    device = disable_device(session=session, device=device)
    return device


@app.post("/admin/expire-users")
def expire_users(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin),
) -> dict:
    now = datetime.utcnow()

    expired_users = session.exec(
        select(User)
        .where(User.is_active == True)
        .where(User.expires_at <= now)
    ).all()

    disabled_device_count = 0

    for user in expired_users:
        enabled_devices = session.exec(
            select(Device)
            .where(Device.user_id == user.id)
            .where(Device.is_enabled == True)
        ).all()

        for device in enabled_devices:
            disable_device(session=session, device=device)
            disabled_device_count += 1

        user.is_active = False
        session.add(user)

    session.commit()

    if len(expired_users) > 0 or disabled_device_count > 0:
        write_action_log(session=session, action="expire_cleanup", message=f"到期清理处理用户 {len(expired_users)} 个，禁用设备 {disabled_device_count} 台")

    return {
        "expired_user_count": len(expired_users),
        "disabled_device_count": disabled_device_count,
    }
