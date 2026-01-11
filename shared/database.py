"""
Модуль для работы с бд
"""
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Импортируем конфигурацию
from config import (
    DATABASE_CONFIG,
    SERVICES_CONFIG,
    LOGGING_CONFIG
)

# Настройка логирования
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Получаем URL базы данных из конфигурации
DATABASE_URL = DATABASE_CONFIG["url"]

logger.info(
    f"Подключение к базе данных PostgreSQL: {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}")


def create_database_engine():
    """
    Создание engine для PostgreSQL с настройками
    """
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_size=20,  # Размер пула соединений
            max_overflow=30,  # Максимальное количество соединений сверх pool_size
            pool_pre_ping=True,  # Проверка соединений перед использованием
            pool_recycle=3600,  # Пересоздание соединений каждый час
            echo=SERVICES_CONFIG["debug"],  # Логирование SQL запросов в debug режиме
            echo_pool=SERVICES_CONFIG["debug"],  # Логирование пула соединений
            connect_args={
                "connect_timeout": 10,
                "application_name": "quest_board"
            }
        )

        # Проверяем подключение
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f" PostgreSQL подключен: {version.split(',')[0]}")

        return engine

    except Exception as e:
        logger.error(f" Ошибка подключения к PostgreSQL: {e}")
        logger.error(
            f"Проверьте что PostgreSQL запущен и доступен по адресу: {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}")
        logger.error(f"База данных: {DATABASE_CONFIG['database']}")
        logger.error(f"Пользователь: {DATABASE_CONFIG['user']}")
        raise


# Создаем engine
engine = create_database_engine()

# Создаем фабрику сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Базовый класс для моделей
Base = declarative_base()


def get_db():
    """
    Dependency для получения сессии базы данных
    Используется в FastAPI Depends
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Контекстный менеджер для работы с сессией базы данных
    Используется вне FastAPI зависимостей
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка в сессии базы данных: {e}")
        raise
    finally:
        db.close()


def init_database():
    """
    Инициализация базы данных - создание всех таблиц
    """
    try:
        # Импортируем все модели для их регистрации
        from shared.models import User, Task, ChatMessage

        # Создаем все таблицы
        logger.info("Создание таблиц базы данных...")
        Base.metadata.create_all(bind=engine)
        logger.info(" Таблицы базы данных успешно созданы")

        # Создаем индексы для улучшения производительности
        with engine.connect() as conn:
            # Индекс для поиска пользователей по username и email
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);
                CREATE INDEX IF NOT EXISTS idx_tasks_creator ON tasks(creator_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_executor ON tasks(executor_id);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_task ON chat_messages(task_id);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at DESC);
            """))
            conn.commit()
        logger.info(" Индексы созданы")

        return True

    except Exception as e:
        logger.error(f" Ошибка инициализации базы данных: {e}")
        return False


def check_database_connection():
    """
    Проверка подключения к базе данных
    """
    try:
        with engine.connect() as conn:
            # Проверяем подключение и получаем информацию о БД
            result = conn.execute(text("""
                    SELECT 
                        current_database() as db_name,
                        current_user as db_user,
                        inet_server_addr() as db_host,
                        inet_server_port() as db_port
                """))
            info = result.fetchone()

            logger.info(f" Подключение к базе данных успешно:")
            logger.info(f"   База данных: {info.db_name}")
            logger.info(f"   Пользователь: {info.db_user}")
            logger.info(f"   Хост: {info.db_host}")
            logger.info(f"   Порт: {info.db_port}")

        return True
    except Exception as e:
        logger.error(f" Ошибка подключения к базе данных: {e}")
        return False


# Проверяем подключение при импорте модуля
if __name__ != "__main__":
    check_database_connection()

