from .types import RabbitMQConfig
from pika import (
    BlockingConnection,
    ConnectionParameters,
    PlainCredentials,
    SSLOptions,
)
from pika.adapters.blocking_connection import BlockingChannel
from types import TracebackType
from typing import (
    LiteralString,
    Optional,
    Type,
)
import ssl

class RabbitMQBaseClient:
    _CONTENT_TYPE: LiteralString = "application/json"
    _DEFAULT_EXCHANGE: LiteralString = ""

    def __init__(
        self,
        queue: str,
        rabbitmq_config: RabbitMQConfig,
        exchange: Optional[str] = None,
        exchange_type: str = "direct",
        routing_key: Optional[str] = None,
        auto_delete_queue: bool = False,
    ) -> None:
        self._queue = queue
        self._prefetch_count = rabbitmq_config["prefetch_count"]
        self._exchange = exchange if exchange is not None else self._DEFAULT_EXCHANGE
        self._exchange_type = exchange_type
        self._routing_key = routing_key if routing_key is not None else queue
        self._connection: Optional[BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None
        self._auto_delete = auto_delete_queue
        
        # Create credentials
        credentials = PlainCredentials(rabbitmq_config["username"], rabbitmq_config["password"])
        
        # Configure TLS if enabled
        if rabbitmq_config["use_tls"]:
            ssl_context = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=str(rabbitmq_config["ca_cert"]) if rabbitmq_config["ca_cert"] else None
            )
            
            # Load client certificate if provided
            if rabbitmq_config["client_cert"] and rabbitmq_config["client_key"]:
                ssl_context.load_cert_chain(
                    certfile=str(rabbitmq_config["client_cert"]),
                    keyfile=str(rabbitmq_config["client_key"])
                )
            
            # For development, you might want to disable hostname checking
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            ssl_options = SSLOptions(ssl_context, rabbitmq_config["host"])
        else:
            ssl_options = None
        
        # Create connection parameters
        self._params = ConnectionParameters(
            host=rabbitmq_config["host"],
            port=rabbitmq_config["port"],
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=600,
            blocked_connection_timeout=300,
        )

    def __enter__(self):
        """Context manager entry."""
        self._connect()
        return self
    
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager exit."""
        self._close()
        return None

    def _connect(self) -> None:
        """Establish connection to RabbitMQ"""
        self._connection = BlockingConnection(self._params)
        self._channel = self._connection.channel()
        
        # Set QoS (prefetch count)
        self._channel.basic_qos(prefetch_count=self._prefetch_count)
        
        # Declare queue (idempotent)
        self._channel.queue_declare(
            queue=self._queue, 
            durable=True,
            auto_delete=self._auto_delete,
        )

        # If using custom exchange, bind queue to exchange
        if not self._is_default_exchange():
            self._channel.exchange_declare(
                exchange=self._exchange,
                exchange_type=self._exchange_type,
                durable=True
            )
            self._channel.queue_bind(
                exchange=self._exchange,
                queue=self._queue,
                routing_key=self._routing_key
            )

    def _close(self) -> None:
        """Close connection"""
        if self._connection and not self._connection.is_closed:
            self._connection.close()

    def _is_default_exchange(self) -> bool:
        """Check if using default exchange."""
        return self._exchange == self._DEFAULT_EXCHANGE