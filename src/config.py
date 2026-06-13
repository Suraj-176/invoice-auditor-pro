"""
Configuration manager for Invoice Auditor Pro
Loads and validates environment variables with sensible defaults
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

class Config:
    """Centralized configuration management"""
    
    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0"))
    
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")
    
    # Database Configuration
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "db/compliance.db")
    DATABASE_BACKUP_PATH: str = os.getenv("DATABASE_BACKUP_PATH", "db/backups")
    DATABASE_RETENTION_DAYS: int = int(os.getenv("DATABASE_RETENTION_DAYS", "730"))
    
    # GST Server Configuration
    GST_SERVER_HOST: str = os.getenv("GST_SERVER_HOST", "127.0.0.1")
    GST_SERVER_PORT: int = int(os.getenv("GST_SERVER_PORT", "8080"))
    GST_SERVER_DEBUG: bool = os.getenv("GST_SERVER_DEBUG", "False").lower() == "true"
    
    # Application Configuration
    HIGH_VALUE_THRESHOLD: float = float(os.getenv("HIGH_VALUE_THRESHOLD", "1000000"))
    HIGH_VALUE_CURRENCY: str = os.getenv("HIGH_VALUE_CURRENCY", "INR")
    CONFIDENCE_THRESHOLD_APPROVED: float = float(os.getenv("CONFIDENCE_THRESHOLD_APPROVED", "0.9"))
    CONFIDENCE_THRESHOLD_HOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD_HOLD", "0.7"))
    CONFIDENCE_THRESHOLD_ESCALATE: float = float(os.getenv("CONFIDENCE_THRESHOLD_ESCALATE", "0.5"))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/invoice_auditor.log")
    LOG_MAX_SIZE_MB: int = int(os.getenv("LOG_MAX_SIZE_MB", "10"))
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    
    # Performance Configuration
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_QUERY_TIMEOUT_SECONDS: int = int(os.getenv("DB_QUERY_TIMEOUT_SECONDS", "30"))
    BATCH_PROCESSING_CHUNK_SIZE: int = int(os.getenv("BATCH_PROCESSING_CHUNK_SIZE", "10"))
    
    # Feature Flags
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "True").lower() == "true"
    ENABLE_BATCH_PROCESSING: bool = os.getenv("ENABLE_BATCH_PROCESSING", "True").lower() == "true"
    ENABLE_OCR_ERROR_CORRECTION: bool = os.getenv("ENABLE_OCR_ERROR_CORRECTION", "True").lower() == "true"
    ENABLE_AUDIT_TRAIL_DETAIL: bool = os.getenv("ENABLE_AUDIT_TRAIL_DETAIL", "True").lower() == "true"
    
    @staticmethod
    def validate_llm_config(provider: str) -> bool:
        """Validate that required API keys exist for the selected provider"""
        validators = {
            "openai": lambda: Config.OPENAI_API_KEY is not None,
            "azure": lambda: (Config.AZURE_OPENAI_API_KEY and Config.AZURE_OPENAI_ENDPOINT and Config.AZURE_OPENAI_DEPLOYMENT),
            "gemini": lambda: Config.GOOGLE_API_KEY is not None,
            "claude": lambda: Config.ANTHROPIC_API_KEY is not None,
        }
        
        validator = validators.get(provider.lower())
        if validator is None:
            raise ValueError(f"Unknown LLM provider: {provider}")
        
        return validator()
    
    @staticmethod
    def get_active_llm_providers() -> list:
        """Returns list of configured LLM providers"""
        available = []
        if Config.OPENAI_API_KEY:
            available.append("openai")
        if Config.AZURE_OPENAI_API_KEY and Config.AZURE_OPENAI_ENDPOINT:
            available.append("azure")
        if Config.GOOGLE_API_KEY:
            available.append("gemini")
        if Config.ANTHROPIC_API_KEY:
            available.append("claude")
        return available
