from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL_NAME: str = "qwen-plus"
    DB_PATH: str = "data/wargame.db"
    LOG_DIR: str = "data/logs"
    TURN_TIMEOUT_SEC: int = 30

    model_config = {"env_file": ".env"}


settings = Settings()
