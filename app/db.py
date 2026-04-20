# 这里导入 SQLModel 的核心对象，用来创建数据库引擎和会话。
from sqlmodel import SQLModel, Session, create_engine

# 这里导入我们自己的配置。
from app.config import settings

# 这里创建数据库引擎，SQLite 需要关闭同线程限制，方便本地开发。
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})


# 这里定义一个初始化数据库的函数，启动时会自动建表。
def init_db() -> None:
    # 这里让 SQLModel 根据模型定义自动创建表。
    SQLModel.metadata.create_all(engine)


# 这里定义一个获取数据库会话的函数，API 每次请求都会用到它。
def get_session():
    # 这里创建会话对象，并在请求结束后自动关闭。
    with Session(engine) as session:
        # 这里把会话交给 FastAPI 的依赖系统使用。
        yield session
