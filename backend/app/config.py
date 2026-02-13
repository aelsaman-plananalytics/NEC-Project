"""
Configuration management for NEC Engineering Analysis System.

This module handles environment variable loading and provides a centralized
settings object using Pydantic BaseSettings.
"""

from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from pydantic_settings import BaseSettings
from pydantic import field_validator
from dotenv import load_dotenv

# Load .env from backend/ first, then from project root (so one .env at root works)
load_dotenv()
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
if _root_env.is_file():
    load_dotenv(dotenv_path=_root_env)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses Pydantic BaseSettings to automatically load from environment
    variables with optional .env file support.
    """
    
    DATABASE_URL: str
    """PostgreSQL database connection URL with SSL mode required."""
    
    OPENAI_API_KEY: str = ""
    """OpenAI API key for LLM validation services (legacy)."""
    
    # Azure OpenAI settings
    AZURE_OPENAI_ENDPOINT: str = ""
    """Azure OpenAI endpoint URL."""
    
    AZURE_OPENAI_API_KEY: str = ""
    """Azure OpenAI API key."""
    
    AZURE_OPENAI_DEPLOYMENT_NAME: str = ""
    """Azure OpenAI deployment name (e.g., gpt-4.1)."""
    
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    """Azure OpenAI API version."""
    
    VECTOR_DB_URL: str = ""
    """Qdrant vector database URL (optional)."""
    
    REDIS_URL: str = ""
    """Redis connection URL for caching and task queues (optional)."""
    
    DEBUG: bool = True
    """Debug mode flag. Set to False in production."""

    JWT_SECRET_KEY: str = "change-me-in-production-use-env"
    """Secret key for JWT signing. Set JWT_SECRET_KEY in production."""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    EMAIL_VERIFICATION_API_KEY: str = ""
    """Optional ZeroBounce API key for email verification at signup. If set, only deliverable emails are accepted."""

    # SMTP for verification emails (production-grade; no Resend)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    """From address for verification emails (e.g. noreply@yourdomain.com)."""

    FRONTEND_BASE_URL: str = "http://localhost:3000"
    """Base URL of the frontend app, used for verification links in email (e.g. https://app.example.com)."""

    REQUIRE_EMAIL_VERIFICATION: bool = False
    """If False, users can sign in without verifying email (e.g. when no SMTP provider is configured). Set True when email sending is in place."""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_ssl_mode(cls, v: str) -> str:
        """
        Ensure DATABASE_URL ends with ?sslmode=require for secure connections.
        
        If the URL already has query parameters, sslmode=require is added or
        updated. If no query parameters exist, ?sslmode=require is appended.
        
        Also auto-fixes common issues like unencoded @ symbols in passwords.
        
        Args:
            v: The database URL from environment variable
            
        Returns:
            str: Database URL with sslmode=require parameter
        """
        if not v:
            return v
        
        # Fix: Remove "DATABASE_URL=" prefix if present (common .env file issue)
        if v.startswith("DATABASE_URL="):
            v = v[13:]  # Remove "DATABASE_URL=" prefix
        
        # Strip whitespace
        v = v.strip()
        
        # Basic URL format validation
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError(
                f"DATABASE_URL must start with 'postgresql://' or 'postgresql+psycopg2://'. "
                f"Current value starts with: {v[:20]}..."
            )
        
        # Auto-fix: Check for unencoded @ symbols in password (common issue)
        # Count @ symbols - should be exactly 1 (between credentials and host)
        at_count = v.count("@")
        if at_count > 1:
            # Try to auto-fix by URL-encoding @ symbols in the password part
            try:
                # Find scheme end
                scheme_end = v.find("://")
                if scheme_end == -1:
                    raise ValueError("Invalid URL scheme")
                scheme_end += 3
                
                # Find the last @ (this should be the host separator)
                # All @ before this are likely in the password
                last_at = v.rfind("@")
                if last_at <= scheme_end:
                    raise ValueError("Invalid URL structure")
                
                # Extract parts
                scheme = v[:scheme_end]
                credentials_and_host = v[scheme_end:]
                
                # Find where credentials end (last @ before host)
                # Everything before last @ is credentials
                creds_part = credentials_and_host[:credentials_and_host.rfind("@")]
                host_and_rest = credentials_and_host[credentials_and_host.rfind("@") + 1:]
                
                # Split credentials into user:password
                if ":" not in creds_part:
                    raise ValueError("No password separator found")
                
                user, password = creds_part.split(":", 1)
                # URL-encode the password (this will encode @, #, %, etc.)
                password_encoded = quote(password, safe="")
                
                # Reconstruct URL
                v = f"{scheme}{user}:{password_encoded}@{host_and_rest}"
                
                # Verify fix worked - should have exactly 1 @ now
                if v.count("@") != 1:
                    raise ValueError(f"Auto-fix failed: still has {v.count('@')} @ symbols")
                    
            except Exception as fix_error:
                raise ValueError(
                    f"Could not auto-fix DATABASE_URL with {at_count} '@' symbols. "
                    f"Please manually URL-encode '@' in password as '%40'. "
                    f"Example: postgresql://user:P%40ssw0rd@host/db. "
                    f"Error: {fix_error}"
                )
        
        # Parse the URL
        try:
            parsed = urlparse(v)
        except Exception as e:
            raise ValueError(f"DATABASE_URL is malformed and cannot be parsed: {e}")
        
        # Ensure sslmode=require is set
        query_params = parse_qs(parsed.query)
        query_params["sslmode"] = ["require"]
        
        # Reconstruct the URL with updated query parameters
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Global settings instance
settings = Settings()

