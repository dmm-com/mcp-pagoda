from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class ServerSettings(BaseSettings):
    # Server settings
    host: str = "localhost"
    port: int = 8000
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")

    def __init__(self, **data):
        """Initialize settings with values from environment variables."""
        super().__init__(**data)
