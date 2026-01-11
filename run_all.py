import subprocess
import time
import sys
import os
from pathlib import Path


def start_service(service_name, port):
    """Запуск микросервиса"""
    print(f"Запуск {service_name} на порту {port}...")

    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path.cwd())

    return subprocess.Popen(
        [sys.executable, '-m', 'uvicorn',
         f'{service_name}.main:app',
         '--host', '0.0.0.0',
         '--port', str(port),
         '--reload'],
        env=env
    )


def main():
    """Главная функция запуска всех сервисов"""
    services = [
        ('auth_service', 8001),
        ('quest_service', 8002),
        ('chat_service', 8003),
        ('notification_service', 8004),
        ('api_gateway', 8000),
    ]

    processes = []

    try:
        # Запускаем все сервисы
        for service_name, port in services:
            proc = start_service(service_name, port)
            processes.append(proc)
            time.sleep(2)  # Пауза между запусками

        print("\n" + "=" * 50)
        print("Все сервисы запущены:")
        print("=" * 50)
        print("API Gateway: http://localhost:8000")
        print("Auth Service: http://localhost:8001")
        print("Quest Service: http://localhost:8002")
        print("Chat Service: http://localhost:8003")
        print("Notification Service: http://localhost:8004")
        print("\nДокументация API: http://localhost:8000/docs")
        print("Для остановки нажмите Ctrl+C")
        print("=" * 50)

        # Ожидаем завершения
        for proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print("\nОстановка сервисов...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        print("Все сервисы остановлены.")
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
        for proc in processes:
            proc.terminate()


if __name__ == '__main__':
    main()
