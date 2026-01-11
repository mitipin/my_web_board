from pathlib import Path

# Базовый путь проекта
BASE_DIR = Path(__file__).parent

# Настройки бд в PostgreSQL
DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "quest_board",
    "user": "postgres",
    "password": "5550444",
    # Формируем URL для SQLAlchemy
    "url": "postgresql://postgres:5550444@localhost:5432/quest_board"
}

# JWT настройки
JWT_CONFIG = {
    "secret_key": "pass12345!",
    "algorithm": "HS256",
    "access_token_expire_minutes": 30
}

# RabbitMQ настройки
RABBITMQ_CONFIG = {
    "enabled": False,
    "host": "localhost",
    "port": 5672,
    "user": "guest",
    "password": "guest"
}


# Настройки сервисов
SERVICES_CONFIG = {
    "auth_port": 8001,
    "quest_port": 8002,
    "chat_port": 8003,
    "notification_port": 8004,
    "api_gateway_port": 8000,
    "debug": True,
    "log_level": "INFO"
}

# Настройки приложения
APP_CONFIG = {
    "title": "Quest Board API",
    "description": "Веб-сервис квест-доски с чатом для выполнения заданий",
    "version": "1.0.0",
    "contact": {
        "name": "Quest Board Team",
        "email": "support@questboard.local"
    }
}

# Настройки безопасности
SECURITY_CONFIG = {
    "password_min_length": 8,
    "password_hash_rounds": 12,
    "session_timeout_hours": 24
}

# Пути к файлам
PATHS = {
    "database_file": BASE_DIR / "quest_board.db",
    "logs_dir": BASE_DIR / "logs",
    "migrations_dir": BASE_DIR / "migrations"
}

# Настройки логирования
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard"
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": PATHS["logs_dir"] / "quest_board.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "detailed"
        }
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "sqlalchemy": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False
        }
    }
}

def setup_directories():
    """Создание необходимых директорий"""
    PATHS["logs_dir"].mkdir(exist_ok=True)
    print(f"📁 Директория логов: {PATHS['logs_dir']}")

def get_database_url():
    """Получение URL базы данных"""
    return DATABASE_CONFIG["url"]

def get_jwt_secret():
    """Получение секретного ключа JWT"""
    return JWT_CONFIG["secret_key"]

def get_rabbitmq_config():
    """Получение конфигурации RabbitMQ"""
    return RABBITMQ_CONFIG

def is_debug():
    """Проверка режима отладки"""
    return SERVICES_CONFIG["debug"]

def get_log_level():
    """Получение уровня логирования"""
    return SERVICES_CONFIG["log_level"]

# Создаем директории при импорте модуля
setup_directories()
