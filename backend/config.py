"""
Configuration settings for OptionsFlow Backend
"""
import os
from datetime import timedelta

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/optionsflow.db")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "optionsflow-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# CORS settings
CORS_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# API settings
API_PREFIX = "/api/v1"
PROJECT_NAME = "OptionsFlow API"
VERSION = "1.0.0"

# Rate limiting
RATE_LIMIT_PER_MINUTE = 60

# Cache settings - reduce external API calls on page refresh
CACHE_TTL_STOCK = int(os.getenv("CACHE_TTL_STOCK", "600"))  # 10 min for stock/ETF info (reduce Yahoo rate limit)
CACHE_TTL_OPTION_CHAIN = int(os.getenv("CACHE_TTL_OPTION_CHAIN", "180"))  # 3 min for option chain
CACHE_TTL_EXPIRATIONS = int(os.getenv("CACHE_TTL_EXPIRATIONS", "600"))  # 10 min for exp dates
CACHE_TTL_RATE = int(os.getenv("CACHE_TTL_RATE", "600"))  # 10 min for risk-free rate
