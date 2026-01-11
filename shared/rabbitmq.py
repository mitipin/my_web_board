"""
Клиент для работы с RabbitMQ
"""
import json
import logging
from config import RABBITMQ_CONFIG
import pika

logger = logging.getLogger(__name__)

class RabbitMQClient:
    """Клиент для работы с RabbitMQ"""

    def __init__(self):
        self.is_enabled = RABBITMQ_CONFIG["enabled"]

        if self.is_enabled:
            try:
                import pika
                self.pika = pika

                self.connection_params = pika.ConnectionParameters(
                    host=RABBITMQ_CONFIG["host"],
                    port=RABBITMQ_CONFIG["port"],
                    credentials=pika.PlainCredentials(
                        RABBITMQ_CONFIG["user"],
                        RABBITMQ_CONFIG["password"]
                    ),
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                logger.info(f"RabbitMQ клиент инициализирован для {RABBITMQ_CONFIG['host']}:{RABBITMQ_CONFIG['port']}")
            except ImportError:
                logger.warning("RabbitMQ (pika) не установлен, используется заглушка")
                self.is_enabled = False
            except Exception as e:
                logger.error(f"Ошибка инициализации RabbitMQ: {e}")
                self.is_enabled = False
        else:
            logger.info("RabbitMQ отключен в конфигурации, используется заглушка")

    def publish_message(self, exchange: str, routing_key: str, message: dict):
        """Публикация сообщения в RabbitMQ или логирование если отключен"""
        try:
            if not self.is_enabled:  # Изменено с enabled на is_enabled
                logger.debug(f"RabbitMQ отключен. Сообщение: {exchange}.{routing_key} - {message}")
                return True



            connection = pika.BlockingConnection(self.connection_params)
            channel = connection.channel()

            # Объявляем exchange если его нет
            channel.exchange_declare(
                exchange=exchange,
                exchange_type='topic',
                durable=True
            )

            # Публикуем сообщение
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(
                delivery_mode=2,  # Сохранять сообщение
                content_type='application/json'
                )
            )

            connection.close()
            logger.info(f"Сообщение отправлено в {exchange}.{routing_key}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в RabbitMQ: {e}")
            logger.debug(f"Сообщение сохранено в логе: {message}")
            return False

    def consume_messages(self, exchange: str, queue_name: str,
                        routing_key: str, callback):
        """Потребление сообщений из RabbitMQ"""
        if not self.is_enabled:  # Изменено с enabled на is_enabled
            logger.warning(f"RabbitMQ отключен, потребление сообщений невозможно")
            return

        try:
            import pika

            def on_message(channel, method, properties, body):
                """Обработка входящего сообщения"""
                try:
                    message = json.loads(body)
                    logger.info(f"Получено сообщение: {method.routing_key}")
                    callback(message)
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {e}")
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


            connection = pika.BlockingConnection(self.connection_params)
            channel = connection.channel()

            # Объявляем exchange
            channel.exchange_declare(
                exchange=exchange,
                exchange_type='topic',
                durable=True
            )

            # Объявляем очередь
            channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={'x-max-length': 10000}
            )

            # Привязываем очередь к exchange
            channel.queue_bind(
                exchange=exchange,
                queue=queue_name,
                routing_key=routing_key
            )

            # Начинаем потребление
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=queue_name,
                on_message_callback=on_message
            )

            logger.info(f"Начато потребление сообщений из {queue_name} ({routing_key})")
            channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Потребление сообщений остановлено пользователем")
        except Exception as e:
            logger.error(f"Ошибка потребления сообщений: {e}")

# Глобальный экземпляр клиента
rabbitmq_client = RabbitMQClient()
