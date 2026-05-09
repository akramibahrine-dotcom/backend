"""Pytest configuration and fixtures."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://baytseha:baytseha_dev@localhost:5432/baytseha_test")
os.environ.setdefault("RUN_MIGRATIONS_ON_START", "false")
os.environ.setdefault("MAXMIND_ACCOUNT_ID", "")
os.environ.setdefault("MAXMIND_LICENSE_KEY", "")
