"""
FloraChain B2B — Application Configuration
Phase 13: Centralized Environment Configurations & dotenv integration
"""

import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_DB_PATH = os.path.join(DATA_DIR, 'florachain.db')

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_file = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    pass


class Config:
    """Base configuration with secure defaults."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'florachain_b2b_dev_secret_key_2026')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    CSRF_ENABLED = True
    
    DB_PATH = os.environ.get('FLORACHAIN_DB_PATH', DEFAULT_DB_PATH)
    DATABASE_URL = os.environ.get('DATABASE_URL', None)
    ALLOW_DEMO_ROLE_SWITCH = False
    TESTING = False
    DEBUG = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    ALLOW_DEMO_ROLE_SWITCH = os.environ.get('FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH', 'true').lower() in ('1', 'true', 'yes')
    SESSION_COOKIE_SECURE = False
    CSRF_ENABLED = True
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing environment configuration with isolated execution settings."""
    TESTING = True
    DEBUG = True
    ALLOW_DEMO_ROLE_SWITCH = True
    SECRET_KEY = 'test-phase13-secret-key-verified'
    SESSION_COOKIE_SECURE = False
    CSRF_ENABLED = False
    LOG_LEVEL = 'WARNING'


class ProductionConfig(Config):
    """Production configuration with strict security posture."""
    DEBUG = False
    TESTING = False
    ALLOW_DEMO_ROLE_SWITCH = False
    SESSION_COOKIE_SECURE = True
    CSRF_ENABLED = True
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """
    Resolves the configuration class based on config_name or FLASK_ENV environment variable.
    """
    if not config_name:
        config_name = os.environ.get('FLASK_ENV', os.environ.get('FLASK_CONFIG', 'default')).lower()
    return config_by_name.get(config_name, DevelopmentConfig)

