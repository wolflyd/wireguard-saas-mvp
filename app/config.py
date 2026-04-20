import os
from dotenv import load_dotenv


load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./wireguard_saas.db")
    WG_SERVER_ENDPOINT: str = os.getenv("WG_SERVER_ENDPOINT", "")
    WG_SERVER_PUBLIC_KEY: str = os.getenv("WG_SERVER_PUBLIC_KEY", "")
    WG_DNS: str = os.getenv("WG_DNS", "1.1.1.1")
    WG_INTERFACE: str = os.getenv("WG_INTERFACE", "wg0")
    WG_NETWORK_CIDR: str = os.getenv("WG_NETWORK_CIDR", "10.0.0.0/24")
    WG_SERVER_TUN_IP: str = os.getenv("WG_SERVER_TUN_IP", "10.0.0.1/24")
    WG_ALLOWED_IPS: str = os.getenv("WG_ALLOWED_IPS", "0.0.0.0/0, ::/0")
    WG_PERSISTENT_KEEPALIVE: int = int(os.getenv("WG_PERSISTENT_KEEPALIVE", "25"))
    WG_APPLY_CHANGES: bool = os.getenv("WG_APPLY_CHANGES", "false").lower() == "true"
    MAX_DEVICES_PER_USER: int = int(os.getenv("MAX_DEVICES_PER_USER", "2"))

    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "change_me_123456")


settings = Settings()
