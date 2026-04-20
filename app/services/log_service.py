# 这里导入会话类型，后面要把日志写进数据库。
from sqlmodel import Session  # 这里导入数据库会话类型。

# 这里导入日志表模型。
from app.models import ActionLog  # 这里导入操作日志表。


# 这里定义一个小函数，用来统一写操作日志。
def write_action_log(
    session: Session,  # 这里接收数据库会话。
    action: str,  # 这里接收动作名称。
    user_id: int | None = None,  # 这里接收用户 id。
    device_id: int | None = None,  # 这里接收设备 id。
    message: str = "",  # 这里接收说明文字。
) -> ActionLog:  # 这里返回刚写入的日志对象。
    # 这里创建一条新的日志记录。
    log = ActionLog(  # 这里开始创建日志对象。
        action=action,  # 这里写入动作名称。
        user_id=user_id,  # 这里写入用户 id。
        device_id=device_id,  # 这里写入设备 id。
        message=message,  # 这里写入说明文字。
    )  # 这里结束日志对象创建。

    # 这里把日志加入数据库会话。
    session.add(log)  # 这里把日志对象放进当前会话。

    # 这里提交事务，把日志真正写进数据库。
    session.commit()  # 这里执行提交。

    # 这里刷新对象，拿到数据库中的最新值。
    session.refresh(log)  # 这里刷新日志对象。

    # 这里返回刚写好的日志。
    return log  # 这里返回日志对象。
