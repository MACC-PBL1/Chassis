from .client import RabbitMQBaseClient
from .types import (
    MessageType,
    RabbitMQConfig,
)
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import (
    Basic,
    BasicProperties,
)
from typing import (
    Callable,
    Optional,
)
import json
import logging

class RabbitMQListener(RabbitMQBaseClient):
    class OneUseInterrupt(Exception):
        pass

    """RabbitMQ listener with TLS support"""
    def __init__(
        self,
        logger: logging.Logger,
        queue: str,
        rabbitmq_config: RabbitMQConfig,
        exchange: Optional[str] = None,
        exchange_type: str = "direct",
        routing_key: Optional[str] = None,
        auto_delete_queue: bool = False,
    ) -> None:
        super().__init__(
            queue=queue, 
            rabbitmq_config=rabbitmq_config,
            exchange=exchange,
            exchange_type=exchange_type,
            routing_key=routing_key,
            auto_delete_queue=auto_delete_queue,
        )
        self._logger = logger

    def _parse_json(
        self, 
        body: bytes, 
        content_type: str
    ) -> MessageType:
        assert content_type == RabbitMQBaseClient._CONTENT_TYPE, "Only valid content should be processed."
        decoded_str = body.decode()
        return json.loads(decoded_str)

    def consume(
        self,
        callback: Callable[[MessageType, str], None],
        auto_ack: bool = False,
        one_use: bool = False,
    ) -> None:
        def _on_message(
            ch: BlockingChannel,
            method: Basic.Deliver,
            properties: BasicProperties,
            body: bytes
        ) -> None:
            try:
                assert properties.content_type is not None, "Content type must be set."
                message = self._parse_json(
                    body=body,
                    content_type=properties.content_type,
                )
                callback(message, self._queue)
                if not auto_ack:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                if one_use:
                    raise RabbitMQListener.OneUseInterrupt
            except RabbitMQListener.OneUseInterrupt:
                raise
            except Exception as e:
                self._logger.error(f"[LOG:CHASSIS:RABBITMQ_LISTENER] - Failed to process message: Reason={e}", exc_info=True)
                if not auto_ack:
                    ch.basic_nack(
                        delivery_tag=method.delivery_tag,
                        requeue=False
                    )                

        if self._channel is None:
            raise RuntimeError("Not connected. Make sure it is connected.")
        
        # Start consuming
        self._channel.basic_consume(
            queue=self._queue,
            on_message_callback=_on_message,
            auto_ack=auto_ack,
        )

        self._logger.info(f"[LOG:CHASSIS:RABBITMQ_LISTENER] - Started consuming from queue: {self._queue}")
        try:
            self._channel.start_consuming()
        except RabbitMQListener.OneUseInterrupt:
            self._logger.info("[LOG:CHASSIS:RABBITMQ_LISTENER] - One-use interrupt")
        except KeyboardInterrupt:
            self._logger.info("[LOG:CHASSIS:RABBITMQ_LISTENER] - Interrupted by user")
        finally:
            self._channel.stop_consuming()

#### EXAMPLES
# # Custom topic exchange (automatic binding)
# listener = RabbitMQListener(
#     logger=logger,
#     queue="logs_queue",
#     rabbitmq_config=config,
#     exchange="logs",
#     exchange_type="topic",
#     routing_key="app.*.error"  # Topic pattern
# )