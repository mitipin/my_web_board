"""
Скрипт для настройки PostgreSQL
"""
import sys
import subprocess
import getpass
from config import DATABASE_CONFIG


def run_command(command, input_text=None, capture_output=True):
    """Выполнение shell команды"""
    try:
        result = subprocess.run(
            command,
            input=input_text,
            capture_output=capture_output,
            text=True,
            shell=sys.platform != "win32"
        )
        return result
    except Exception as e:
        print(f" Ошибка выполнения команды: {e}")
        return None


def check_postgres_installed():
    """Проверка установки PostgreSQL"""
    print(" Проверка установки PostgreSQL...")

    # Проверяем psql
    result = run_command(["psql", "--version"])

    if result and result.returncode == 0:
        print(f"PostgreSQL установлен: {result.stdout.strip()}")
        return True
    else:
        print("PostgreSQL не найден")
        return False


def check_postgres_running():
    """Проверка запуска службы PostgreSQL"""
    print("\n Проверка запуска PostgreSQL...")

    result = run_command(["pg_isready", "-h", DATABASE_CONFIG["host"], "-p", str(DATABASE_CONFIG["port"])])

    if result and result.returncode == 0:
        print("PostgreSQL запущен и готов к подключению")
        return True
    else:
        print("PostgreSQL не запущен или недоступен")
        return False


def create_database():
    """Создание базы данных"""
    print(f"\n  Создание базы данных '{DATABASE_CONFIG['database']}'...")

    # Запрашиваем пароль
    password = getpass.getpass(f"Введите пароль пользователя '{DATABASE_CONFIG['user']}': ")

    # Команда для создания базы данных
    create_cmd = [
        "createdb",
        "-h", DATABASE_CONFIG["host"],
        "-p", str(DATABASE_CONFIG["port"]),
        "-U", DATABASE_CONFIG["user"],
        DATABASE_CONFIG["database"],
        "--echo"
    ]

    # Устанавливаем пароль как переменную окружения
    env = {"PGPASSWORD": password}

    try:
        result = subprocess.run(
            create_cmd,
            env=env,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("База данных успешно создана")
            return True, password
        else:
            print(f"Ошибка создания базы данных: {result.stderr}")

            # Пробуем через SQL
            print("Попытка создания через SQL команду...")

            sql_cmd = [
                "psql",
                "-h", DATABASE_CONFIG["host"],
                "-p", str(DATABASE_CONFIG["port"]),
                "-U", DATABASE_CONFIG["user"],
                "-c", f"CREATE DATABASE {DATABASE_CONFIG['database']};"
            ]

            result = subprocess.run(
                sql_cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print("База данных создана через SQL")
                return True, password
            else:
                print(f"Ошибка SQL команды: {result.stderr}")
                return False, None

    except Exception as e:
        print(f"Исключение при создании базы данных: {e}")
        return False, None


def update_config_password(new_password):
    """Обновление пароля в конфигурации"""
    print("\nОбновление конфигурации...")

    try:
        # Обновляем DATABASE_CONFIG
        from config import DATABASE_CONFIG
        DATABASE_CONFIG["password"] = new_password
        DATABASE_CONFIG["url"] = f"postgresql://{DATABASE_CONFIG['user']}:{new_password}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"

        # Обновляем файл config.py
        config_path = "config.py"
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Заменяем пароль в конфигурации
        import re
        old_url_pattern = r"postgresql://[^:]+:[^@]+@[^:]+:\d+/[^\"']+"
        new_url = f"postgresql://{DATABASE_CONFIG['user']}:{new_password}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"

        content = re.sub(old_url_pattern, new_url, content)

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

        print("Конфигурация обновлена")
        return True

    except Exception as e:
        print(f"Ошибка обновления конфигурации: {e}")
        return False


def test_connection(password):
    """Тестирование подключения к базе данных"""
    print("\nТестирование подключения...")

    test_cmd = [
        "psql",
        "-h", DATABASE_CONFIG["host"],
        "-p", str(DATABASE_CONFIG["port"]),
        "-U", DATABASE_CONFIG["user"],
        "-d", DATABASE_CONFIG["database"],
        "-c", "SELECT version();"
    ]

    env = {"PGPASSWORD": password}

    result = subprocess.run(
        test_cmd,
        env=env,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        version_line = result.stdout.strip().split('\n')[2]
        print(f" Подключение успешно: {version_line}")
        return True
    else:
        print(f" Ошибка подключения: {result.stderr}")
        return False


def show_installation_instructions():
    """Показать инструкции по установке PostgreSQL"""
    print("\n" + "=" * 70)
    print("ИНСТРУКЦИИ ПО УСТАНОВКЕ POSTGRESQL")
    print("=" * 70)

    if sys.platform == "win32":
        print("\nДля Windows:")
        print("1. Скачайте установщик: https://www.postgresql.org/download/windows/")
        print("2. Установите с настройками по умолчанию")
        print(f"3. Укажите пароль: {DATABASE_CONFIG['password']}")
        print("4. Порт оставьте: 5432")
        print("5. Добавьте в PATH: C:\\Program Files\\PostgreSQL\\15\\bin")

    elif sys.platform == "darwin":
        print("\nДля macOS:")
        print("1. Установите Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        print("2. Установите PostgreSQL: brew install postgresql@15")
        print("3. Запустите: brew services start postgresql@15")

    else:
        print("\nДля Linux (Ubuntu/Debian):")
        print("1. Обновите пакеты: sudo apt update")
        print("2. Установите PostgreSQL: sudo apt install postgresql postgresql-contrib")
        print("3. Запустите службу: sudo systemctl start postgresql")
        print("4. Включите автозапуск: sudo systemctl enable postgresql")

    print("\nПосле установки запустите этот скрипт снова.")
    print("=" * 70)


def main():
    """Основная функция настройки"""
    print("=" * 70)
    print("НАСТРОЙКА POSTGRESQL ДЛЯ QUEST BOARD")
    print("=" * 70)

    # Проверяем установку PostgreSQL
    if not check_postgres_installed():
        show_installation_instructions()
        return False

    # Проверяем запуск PostgreSQL
    if not check_postgres_running():
        print("\nЗапустите PostgreSQL и попробуйте снова.")
        if sys.platform == "win32":
            print("Команда: net start postgresql-x64-15")
        else:
            print("Команда: sudo systemctl start postgresql")
        return False

    # Создаем базу данных
    success, password = create_database()
    if not success:
        print("\nСоздайте базу данных вручную:")
        print(f"   createdb -U {DATABASE_CONFIG['user']} -h {DATABASE_CONFIG['host']} {DATABASE_CONFIG['database']}")
        return False

    # Обновляем конфигурацию

    if not update_config_password(password):
        print("\n  Обновите конфигурацию вручную в файле config.py")
        print(f"   Установите пароль: {password}")

        # Тестируем подключение
    if not test_connection(password):
        print("\n️  Проверьте настройки доступа в pg_hba.conf")
        return False

    print("\n" + "=" * 70)
    print(" POSTGRESQL УСПЕШНО НАСТРОЕН!")
    print("=" * 70)

    print("\nСледующие шаги:")
    print("1. Инициализируйте базу данных: python init_db.py")
    print("2. Запустите сервисы: python run_all.py")
    print("3. Откройте в браузере: http://localhost:8000/docs")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n  Настройка прервана")
        sys.exit(1)
