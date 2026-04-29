from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL_NAME: str = "qwen-plus"
    SGLANG_BASE_URL: str = ""
    SGLANG_MODEL_NAME: str = ""
    DB_PATH: str = "data/wargame.db"
    LOG_DIR: str = "data/logs"
    TURN_TIMEOUT_SEC: int = 30

    model_config = {"env_file": "../.env"}

    def get_llm_config(self) -> dict:
        """Return LLM config, preferring sGLang if configured."""
        if self.SGLANG_BASE_URL:
            return {
                "api_key": self.SGLANG_BASE_URL and "not-needed",
                "base_url": self.SGLANG_BASE_URL,
                "model": self.SGLANG_MODEL_NAME or self.LLM_MODEL_NAME,
                "temperature": 0.0,
            }
        return {
            "api_key": self.LLM_API_KEY,
            "base_url": self.LLM_BASE_URL,
            "model": self.LLM_MODEL_NAME,
            "temperature": 0.0,
        }


settings = Settings()
