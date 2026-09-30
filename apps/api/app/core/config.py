from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_TZ: str = "Africa/Kigali"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:Postgre123@localhost:5433/garuka"
    JWT_SECRET: str = "change-me-long-jwt-secret-key-min-32-chars"
    JWT_ACCESS_MINUTES: int = 30
    JWT_REFRESH_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:3000"

    # Africa's Talking / USSD
    USSD_WEBHOOK_SECRET: str = "change-me-long-random"
    USSD_SERVICE_CODE_DISPLAY: str = "*384*1234#"
    AT_USERNAME: str = "sandbox"
    AT_API_KEY: str = ""
    AT_SENDER_ID: str = ""
    AT_ALLOWED_IPS: str = ""
    SMS_PROVIDER: str = "console"
    SMS_QUIET_HOURS_START: str = "19:00"
    SMS_QUIET_HOURS_END: str = "07:00"
    LOG_USSD_PHONE: bool = False

    # Rules Engine Defaults
    RULE_CONSECUTIVE_DAYS: int = 3
    RULE_MONTHLY_ABSENCES: int = 5
    RULE_ESCALATE_TERM_ABSENCES: int = 10
    RULE_VISIT_SLA_SCHOOL_DAYS: int = 3
    RULE_RETURN_STREAK_SCHOOL_DAYS: int = 10
    RULE_DISTRICT_ESCALATION_DAYS: int = 14
    RULE_MAX_BACKDATE_SCHOOL_DAYS: int = 2
    MENTOR_MAX_ACTIVE_CASES: int = 15

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
