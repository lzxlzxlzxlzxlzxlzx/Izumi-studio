import os
from pathlib import Path


def _load_dotenv():
    """Load .env file from project root (parent of backend/)."""
    env_path = Path(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    os.environ[key] = value


_load_dotenv()


class Settings:
    app_name: str = "Izumi Studio"
    version: str = "0.1.0"
    debug: bool = True

    data_dir: Path = Path(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    db_path: Path = Path(data_dir, "izumi.db")
    cards_dir: Path = Path(data_dir, "cards")
    uploads_dir: Path = Path(data_dir, "uploads")
    presets_dir: Path = Path(data_dir, "presets")
    worldbooks_dir: Path = Path(data_dir, "worldbooks")
    logs_dir: Path = Path(data_dir, "logs")

    @property
    def deepseek_api_key(self) -> str:
        return os.getenv("API_KEY", "")

    @property
    def deepseek_api_url(self) -> str:
        return os.getenv("API_URL", "https://api.deepseek.com/v1/chat/completions")

    @property
    def dashscope_api_key(self) -> str:
        return os.getenv("DASHSCOPE_API_KEY", os.getenv("DASH_SCOPE_KEY", ""))

    @property
    def dashscope_api_url(self) -> str:
        return os.getenv("DASHSCOPE_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    @property
    def kimi_api_key(self) -> str:
        return os.getenv("KIMI_API_KEY", "")

    @property
    def kimi_api_url(self) -> str:
        return os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1")

    @property
    def claude_api_key(self) -> str:
        return os.getenv("CLAUDE_API_KEY", "")

    @property
    def claude_api_url(self) -> str:
        return os.getenv("CLAUDE_API_URL", "")

    @property
    def backend_port(self) -> int:
        return int(os.getenv("BACKEND_PORT", "8004"))

    @property
    def frontend_port(self) -> int:
        return int(os.getenv("FRONTEND_PORT", "5173"))


settings = Settings()

for d in [settings.data_dir, settings.cards_dir, settings.uploads_dir, settings.presets_dir, settings.worldbooks_dir, settings.logs_dir]:
    d.mkdir(parents=True, exist_ok=True)
