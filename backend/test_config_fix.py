
import os
from app.core.config import Settings

# Test case 1: Render style postgres://
os.environ["DATABASE_URL"] = "postgres://user:pass@host/db"
settings = Settings()
print(f"Input: postgres://user:pass@host/db")
print(f"Output: {settings.DATABASE_URL}")

# Test case 2: Standard postgresql://
os.environ["DATABASE_URL"] = "postgresql://user:pass@host/db"
settings = Settings()
print(f"Input: postgresql://user:pass@host/db")
print(f"Output: {settings.DATABASE_URL}")

# Test case 3: Already correct
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@host/db"
settings = Settings()
print(f"Input: postgresql+asyncpg://user:pass@host/db")
print(f"Output: {settings.DATABASE_URL}")
