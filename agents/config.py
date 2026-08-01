import os
from dataclasses import dataclass
from dotenv import load_dotenv
import clickhouse_connect
from google import genai

load_dotenv()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 8443))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")


@dataclass
class ClickHouseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class LangfuseConfig:
    enabled: bool
    public_key: str
    secret_key: str
    host: str


class OpenRouterConfig:

    def __init__(self, model: str = "gemma-4-26b-a4b-it"):
        self.model = model
        self.api_key = GOOGLE_AI_STUDIO_API_KEY

    def get_client(self):
        # Returns standard Google GenAI Client
        return genai.Client(api_key=self.api_key)


def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
        secure=True if CLICKHOUSE_PORT == 8443 else False,
        connect_timeout=5,  # Prevents hanging indefinitely on connection
        send_receive_timeout=15,
    )


def get_config():
    ch_config = ClickHouseConfig(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )

    lf_config = LangfuseConfig(
        enabled=bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY),
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_BASE_URL,
    )

    or_config = OpenRouterConfig()

    return ch_config, lf_config, or_config