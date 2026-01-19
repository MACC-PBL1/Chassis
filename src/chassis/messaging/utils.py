from .listener import RabbitMQListener
from .types import (
    _HandlerFunc,
    MessageType,
    RabbitMQConfig,
)
from pika import (
    BlockingConnection,
    ConnectionParameters,
    PlainCredentials,
    SSLOptions,
)
from typing import (
    Callable,
    Dict,
    Optional,
    Tuple,
)
import asyncio
import logging
import ssl

# Global Variables ############################################################
logger = logging.getLogger(__name__)
_QUEUE_HANDLERS: Dict[str, Tuple[_HandlerFunc, Optional[Dict[str, str]]]] = {}

# Functions ###################################################################
def register_queue_handler(
    queue: str,
    exchange: Optional[str] = None,
    exchange_type: str = "direct",
    routing_key: Optional[str] = None,
) -> Callable[[_HandlerFunc], _HandlerFunc]:
    def decorator(func: _HandlerFunc) -> _HandlerFunc:
        exchange_config = None
        if exchange is not None:
            exchange_config = {
                "exchange": exchange,
                "exchange_type": exchange_type,
                "routing_key": routing_key if routing_key is not None else queue,
            }
        
        _QUEUE_HANDLERS[queue] = (func, exchange_config)
        handler_type = "async" if asyncio.iscoroutinefunction(func) else "sync"
        exchange_info = f" (exchange: {exchange}, type: {exchange_type})" if exchange else " (default exchange)"
        logger.info(f"[LOG:CHASSIS:RABBITMQ_UTILS] - Registered {handler_type} handler for queue: {queue}{exchange_info}")
        return func
    return decorator

def _process_message(message: MessageType, queue: str):
    """Process incoming RabbitMQ messages."""
    try:
        handler, _ = _QUEUE_HANDLERS[queue]
        if asyncio.iscoroutinefunction(handler):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(handler(message))
            except RuntimeError:
                # No running loop - create a new one with proper context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(handler(message))
                finally:
                    # Clean up the loop after the handler completes
                    try:
                        loop.run_until_complete(loop.shutdown_asyncgens())
                    finally:
                        loop.close()
                        asyncio.set_event_loop(None)
        else:
            handler(message)
    except Exception as e:
        logger.error(f"[LOG:CHASSIS:RABBITMQ_UTILS] - Error processing event: Reason={e}", exc_info=True)
        raise

def start_rabbitmq_listener(
    queue: str,
    config: RabbitMQConfig,
    one_use: bool = False,
) -> None:
    """
    Start RabbitMQ listener in a separate thread.
    Uses exchange configuration from the registered handler decorator.
    """
    try:
        # Get the exchange configuration for this queue
        if queue not in _QUEUE_HANDLERS:
            raise ValueError(f"No handler registered for queue: {queue}")
        
        _, exchange_config = _QUEUE_HANDLERS[queue]
        
        # Create listener with appropriate exchange configuration
        listener_kwargs = {
            "logger": logger,
            "queue": queue,
            "rabbitmq_config": config,
        }
        
        if exchange_config:
            listener_kwargs.update(exchange_config)
        
        with RabbitMQListener(**listener_kwargs) as listener:
            logger.info(f"[LOG:CHASSIS:RABBITMQ_UTILS] - RabbitMQ listener connected to queue: {queue}")
            listener.consume(
                callback=_process_message, 
                one_use=one_use
            )
    except KeyboardInterrupt:
        logger.info("[LOG:CHASSIS:RABBITMQ_UTILS] - RabbitMQ listener stopped by keyboard interrupt")
    except Exception as e:
        logger.error(f"[LOG:CHASSIS:RABBITMQ_UTILS] - RabbitMQ listener error: Reason={e}", exc_info=True)
    finally:
        # Delete if queue is one use
        if one_use:
            del _QUEUE_HANDLERS[queue]

def is_rabbitmq_healthy(rabbitmq_config: RabbitMQConfig) -> bool:
    try:
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
        params = ConnectionParameters(
            host=rabbitmq_config["host"],
            port=rabbitmq_config["port"],
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=600,
            blocked_connection_timeout=300,
        )

        connection = BlockingConnection(params)
        channel = connection.channel()

        channel.queue_declare(
            queue="", 
            exclusive=True,
            auto_delete=True,
        )

        channel.close()
        connection.close()
        return True

    except Exception:
        return False