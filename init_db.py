"""
Инициализация базы данных PostgreSQL
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь Python
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем конфигурацию и логирование
from config import LOGGING_CONFIG
import logging.config

# Настраиваем логирование
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

from shared.database import init_database, get_db_session, check_database_connection
from shared.models import User, Task
from shared.security import get_password_hash, validate_password_strength
from config import DATABASE_CONFIG


def print_header():
    """Вывод заголовка"""
    print("=" * 70)
    print("ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ QUEST BOARD")
    print("=" * 70)
    print(f"PostgreSQL: {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}")
    print(f"База данных: {DATABASE_CONFIG['database']}")
    print(f"Пользователь: {DATABASE_CONFIG['user']}")
    print("=" * 70)


def create_admin_user():
    """Создание административного пользователя"""
    try:
        with get_db_session() as db:
            # Проверяем, есть ли уже пользователь admin
            admin = db.query(User).filter(User.username == "admin").first()

            if not admin:
                # Проверяем сложность пароля
                admin_password = "AdminSecure321"
                is_valid, message = validate_password_strength(admin_password)

                if not is_valid:
                    logger.error(f"Пароль администратора не соответствует требованиям: {message}")
                    return False

                admin_user = User(
                    username="admin",
                    email="ekbuzhik@gmail.com",
                    hashed_password=get_password_hash(admin_password),
                    full_name="Администратор системы",
                    balance=100000.0,
                    rating=5.0,
                    is_active=True
                )
                db.add(admin_user)

                print(f"\n Администратор создан:")
                print(f"   Логин: admin")
                print(f"   Пароль: {admin_password}")
                print(f"   Email: ekbuzhik@gmail.com")
                print(f"   Баланс: 100,000.00")

            else:
                print(f"\n  Администратор уже существует: {admin.username}")

            # Создаем тестового пользователя
            test_user = db.query(User).filter(User.username == "test_user").first()
            if not test_user:
                test_password = "TestUser123!"
                is_valid, message = validate_password_strength(test_password)

                if not is_valid:
                    logger.error(f"Пароль тестового пользователя не соответствует требованиям: {message}")
                    return False

                user = User(
                    username="test_user",
                    email="test@questboard.com",
                    hashed_password=get_password_hash(test_password),
                    full_name="Тестовый Пользователь",
                    balance=5000.0,
                    rating=5.0,
                    is_active=True
                )
                db.add(user)

                print(f"\n Тестовый пользователь создан:")
                print(f"   Логин: test_user")
                print(f"   Пароль: {test_password}")
                print(f"   Email: test@questboard.com")
                print(f"   Баланс: 5,000.00")

            else:
                print(f"\n️  Тестовый пользователь уже существует: {test_user.username}")

            logger.info("Пользователи успешно созданы")
            return True

    except Exception as e:
        logger.error(f"Ошибка создания пользователей: {e}")
        return False


def create_sample_tasks():
    """Создание примеров заданий"""
    try:
        from datetime import datetime, timedelta

        with get_db_session() as db:
            # Проверяем, есть ли уже задания
            task_count = db.query(Task).count()

            if task_count == 0:
                # Находим тестового пользователя
                test_user = db.query(User).filter(User.username == "test_user").first()

                if test_user:
                    # Создаем несколько примеров заданий
                    sample_tasks = [
                        Task(
                            title="Разработать логотип для IT-стартапа",
                            description="""Найдите синий камень.""",
                            price=1500.0,
                            category="Добыча",
                            status="open",
                            deadline=datetime.utcnow() + timedelta(days=7),
                            creator_id=test_user.id
                        ),
                        Task(
                            title="Написать статью о животных",
                            description="""Научная статья на 2000+ слов с фотографиями.""",
                            price=2500.0,
                            category="Копирайтинг",
                            status="open",
                            deadline=datetime.utcnow() + timedelta(days=5),
                            creator_id=test_user.id
                        ),
                        Task(
                            title="Убейте босса на 17 этаже",
                            description="""Требуется сердце босса""",
                            price=12000.0,
                            category="Бой", status="in_progress",
                            deadline=datetime.utcnow() + timedelta(days=14),
                            creator_id=test_user.id
                        ),
                        Task(
                            title="Защита повозки",
                            description="""Защитить повозк с ресурсами до границы королевства.""",
                            price=15000.0,
                            category="Защита",
                            status="open",
                            deadline=datetime.utcnow() + timedelta(days=10),
                            creator_id=test_user.id
                        )
                    ]

                    for task in sample_tasks:
                        db.add(task)

                    print(f"\n Создано {len(sample_tasks)} примеров заданий:")
                    for i, task in enumerate(sample_tasks, 1):
                        print(f"   {i}. {task.title} - {task.price:,.0f} руб.")

                else:
                    print("\n️  Тестовый пользователь не найден, задания не созданы")
            else:
                print(f"\nℹ  В базе уже есть {task_count} заданий")

        return True

    except Exception as e:
        logger.error(f"Ошибка создания заданий: {e}")
        return False


def main():
    """Основная функция инициализации"""
    print_header()

    try:
        # 1. Проверяем подключение к базе данных
        print("\n Проверка подключения к PostgreSQL...")
        if not check_database_connection():
            print(" Не удалось подключиться к PostgreSQL")
            print("\nУбедитесь что:")
            print(f"1. PostgreSQL запущен на {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}")
            print(f"2. База данных '{DATABASE_CONFIG['database']}' существует")
            print(f"3. Пользователь '{DATABASE_CONFIG['user']}' имеет доступ")
            print(f"4. Пароль указан верно")
            print("\nДля создания базы данных выполните:")
            print(
                f"   createdb -U {DATABASE_CONFIG['user']} -h {DATABASE_CONFIG['host']} {DATABASE_CONFIG['database']}")
            return False

        # 2. Создаем таблицы
        print("\n  Создание таблиц...")
        if not init_database():
            print(" Ошибка при создании таблиц")
            return False

        # 3. Создаем пользователей
        print("\n Создание пользователей...")
        if not create_admin_user():
            print(" Ошибка при создании пользователей")
            return False

        # 4. Создаем примеры заданий
        print("\n Создание примеров заданий...")
        if not create_sample_tasks():
            print("️  Не удалось создать примеры заданий")

        print("\n" + "=" * 70)
        print(" БАЗА ДАННЫХ УСПЕШНО ИНИЦИАЛИЗИРОВАНА!")
        print("=" * 70)

        print("\n Сводка:")
        print("-" * 40)
        print(" Администратор:")
        print("   • Логин: admin")
        print("   • Пароль: AdminSecure321")
        print("   • Баланс: 100,000.00 руб.")

        print("\n Тестовый пользователь:")
        print("   • Логин: test_user")
        print("   • Пароль: TestUser123!")
        print("   • Баланс: 5,000.00 руб.")

        print("\n Примеры заданий:")
        print("   • 4 задания в разных категориях")
        print("   • Цены от 1,500 до 15,000 руб.")

        print("\n Следующие шаги:")
        print("   1. Запустите сервисы: python run_all.py")
        print("   2. Откройте в браузере: http://localhost:8000/docs")
        print("   3. Используйте тестовые учетные записи")
        print("=" * 70)

        return True

    except KeyboardInterrupt:
        print("\n\n  Инициализация прервана пользователем")
        return False
    except Exception as e:
        print(f"\n Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
