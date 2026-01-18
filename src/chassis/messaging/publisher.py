from .client import RabbitMQBaseClient
from .types import (
    RabbitMQConfig,
    MessageType
)
from pika import BasicProperties
from typing import Optional
import json

class RabbitMQPublisher(RabbitMQBaseClient):
    """RabbitMQ publisher with TLS support"""
    def __init__(
        self,
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

    def publish(
        self,
        message: MessageType,
        routing_key: Optional[str] = None,
        exchange: Optional[str] = None,
        persistent: bool = True,
    ) -> None:
        """
        Publish a message to RabbitMQ.
        
        Args:
            routing_key: Routing key (queue name for default exchange)
            message: Message to publish (will be JSON serialized if dict/list)
            exchange: Exchange name (uses instance default if None)
            persistent: Whether message should survive broker restart
        """
        assert isinstance(message, dict), "'message' must be a dictionary type."
        if self._channel is None or self._connection is None or self._connection.is_closed:
            try:
                self._connect()
            except Exception as e:
                raise RuntimeError(f"Failed to reconnect to RabbitMQ: {e}")

        # Serialize message
        body = json.dumps(message)

        # Message properties
        properties = BasicProperties(
            content_type=super()._CONTENT_TYPE,
            delivery_mode=2 if persistent else 1,
        )

        # Use instance defaults if not provided
        target_exchange = exchange if exchange is not None else self._exchange
        target_routing_key = routing_key if routing_key is not None else self._routing_key

        # Publish message
        assert self._channel is not None, "To publish, a channel must be created"
        self._channel.basic_publish(
            exchange=target_exchange,
            routing_key=target_routing_key,
            body=body,
            properties=properties,
        )

#### Examples
# # Default exchange (no binding)
# publisher = RabbitMQPublisher(
#     queue="my_queue",
#     rabbitmq_config=config
# )

# # Custom direct exchange (automatic binding)
# publisher = RabbitMQPublisher(
#     queue="my_queue",
#     rabbitmq_config=config,
#     exchange="my_exchange",
#     exchange_type="direct",
#     routing_key="my.routing.key"
# )

# # Fanout exchange (binding still needed but routing_key ignored)
# publisher = RabbitMQPublisher(
#     queue="broadcast_queue",
#     rabbitmq_config=config,
#     exchange="notifications",
#     exchange_type="fanout"
# )