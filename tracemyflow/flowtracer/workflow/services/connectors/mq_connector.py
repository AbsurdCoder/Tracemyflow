
import json
import logging
from typing import Dict, List, Optional, Any, Union, Callable
import time

# Create a logger for this module
logger = logging.getLogger(__name__)

class MQConnector:
    """
    Connector for interacting with Message Queues (supports RabbitMQ, ActiveMQ, IBM MQ).
    Provides methods for sending messages to and receiving messages from queues.
    """
    
    # Supported MQ types
    SUPPORTED_TYPES = ['rabbitmq', 'activemq', 'ibmmq']
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the MQ connector with the given configuration.
        
        Args:
            config: A dictionary containing MQ configuration parameters:
                - mq_type: Type of MQ ('rabbitmq', 'activemq', 'ibmmq')
                - host: MQ server hostname
                - port: MQ server port
                - username: Username for authentication
                - password: Password for authentication
                - vhost: Virtual host (for RabbitMQ)
                - queue_manager: Queue manager name (for IBM MQ)
                - channel: Channel name (for IBM MQ)
                - ssl_enabled: Whether to use SSL/TLS
                - ssl_options: SSL/TLS options
        """
        self.config = config
        self.mq_type = config.get('mq_type', 'rabbitmq').lower()
        
        if self.mq_type not in self.SUPPORTED_TYPES:
            logger.warning(f"Unsupported MQ type: {self.mq_type}. Defaulting to RabbitMQ.")
            self.mq_type = 'rabbitmq'
        
        # Common configuration
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', self._get_default_port())
        self.username = config.get('username', 'guest')
        self.password = config.get('password', 'guest')
        self.ssl_enabled = config.get('ssl_enabled', False)
        self.ssl_options = config.get('ssl_options', {})
        
        # RabbitMQ specific
        self.vhost = config.get('vhost', '/')
        
        # IBM MQ specific
        self.queue_manager = config.get('queue_manager', '')
        self.channel = config.get('channel', '')
        
        # Connection/channel objects
        self.connection = None
        self.channel = None
        
        logger.info(f"Initialized {self.mq_type} connector with host: {self.host}")
    
    def _get_default_port(self) -> int:
        """Get the default port for the selected MQ type."""
        if self.mq_type == 'rabbitmq':
            return 5672
        elif self.mq_type == 'activemq':
            return 61616
        elif self.mq_type == 'ibmmq':
            return 1414
        return 5672  # Default to RabbitMQ port
    
    def connect(self) -> bool:
        """
        Establish connection to the message queue.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.mq_type == 'rabbitmq':
                return self._connect_rabbitmq()
            elif self.mq_type == 'activemq':
                return self._connect_activemq()
            elif self.mq_type == 'ibmmq':
                return self._connect_ibmmq()
            else:
                logger.error(f"Unsupported MQ type: {self.mq_type}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to {self.mq_type}: {str(e)}")
            return False
    
    def _connect_rabbitmq(self) -> bool:
        """Connect to RabbitMQ."""
        try:
            import pika
            
            # Prepare credentials and connection parameters
            credentials = pika.PlainCredentials(self.username, self.password)
            
            connection_params = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials
            )
            
            # Add SSL options if enabled
            if self.ssl_enabled:
                ssl_options = pika.SSLOptions(**self.ssl_options)
                connection_params = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.vhost,
                    credentials=credentials,
                    ssl_options=ssl_options
                )
            
            # Establish connection
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            logger.info(f"Successfully connected to RabbitMQ at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            return False
    
    def _connect_activemq(self) -> bool:
        """Connect to ActiveMQ."""
        try:
            import stomp
            
            # Create connection
            conn = stomp.Connection([(self.host, self.port)])
            
            # Connect with credentials
            conn.connect(self.username, self.password, wait=True)
            
            self.connection = conn
            logger.info(f"Successfully connected to ActiveMQ at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ActiveMQ: {str(e)}")
            return False
    
    def _connect_ibmmq(self) -> bool:
        """Connect to IBM MQ."""
        try:
            import pymqi
            
            # Prepare connection info
            conn_info = f'TCP:{self.host}({self.port})'
            
            # Connect to queue manager
            self.connection = pymqi.connect(
                self.queue_manager,
                self.channel,
                conn_info,
                self.username,
                self.password
            )
            
            logger.info(f"Successfully connected to IBM MQ at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBM MQ: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Close connection to the message queue."""
        try:
            if self.mq_type == 'rabbitmq':
                if self.connection and self.connection.is_open:
                    self.connection.close()
            elif self.mq_type == 'activemq':
                if self.connection:
                    self.connection.disconnect()
            elif self.mq_type == 'ibmmq':
                if self.connection:
                    self.connection.disconnect()
            
            self.connection = None
            self.channel = None
            logger.info(f"Disconnected from {self.mq_type}")
        except Exception as e:
            logger.error(f"Error while disconnecting from {self.mq_type}: {str(e)}")
    
    def declare_queue(self, queue_name: str, durable: bool = True, exclusive: bool = False, 
                      auto_delete: bool = False, arguments: Optional[Dict[str, Any]] = None) -> bool:
        """
        Declare a queue.
        
        Args:
            queue_name: Name of the queue to declare
            durable: Whether the queue should survive broker restarts
            exclusive: Whether the queue is exclusive to this connection
            auto_delete: Whether the queue should be deleted when no longer used
            arguments: Additional arguments for queue declaration
            
        Returns:
            bool: True if queue declared successfully, False otherwise
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot declare queue: not connected to {self.mq_type}")
                return False
        
        try:
            if self.mq_type == 'rabbitmq':
                if not self.channel:
                    self.channel = self.connection.channel()
                
                # Declare queue
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=durable,
                    exclusive=exclusive,
                    auto_delete=auto_delete,
                    arguments=arguments or {}
                )
            elif self.mq_type == 'activemq':
                # ActiveMQ creates queues automatically when sending messages
                pass
            elif self.mq_type == 'ibmmq':
                # For IBM MQ, queues are typically defined by an administrator
                pass
            
            logger.info(f"Queue '{queue_name}' declared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to declare queue '{queue_name}': {str(e)}")
            return False
    
    def send_message(self, queue_name: str, message: Dict[str, Any], 
                    properties: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a message to a queue.
        
        Args:
            queue_name: The queue to send the message to
            message: The message payload as a dictionary
            properties: Optional message properties
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot send message: not connected to {self.mq_type}")
                return False
        
        try:
            # Convert message to JSON string
            message_body = json.dumps(message)
            
            if self.mq_type == 'rabbitmq':
                if not self.channel:
                    self.channel = self.connection.channel()
                
                # Send message
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=message_body.encode('utf-8'),
                    properties=self._create_rabbitmq_properties(properties) if properties else None
                )
            elif self.mq_type == 'activemq':
                # Send message to ActiveMQ queue
                self.connection.send(
                    destination=f'/queue/{queue_name}',
                    body=message_body,
                    headers=properties or {}
                )
            elif self.mq_type == 'ibmmq':
                import pymqi
                
                # Create queue object
                queue = pymqi.Queue(self.connection, queue_name)
                
                # Put message
                queue.put(message_body.encode('utf-8'))
                queue.close()
            
            logger.info(f"Message sent to queue '{queue_name}' successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to queue '{queue_name}': {str(e)}")
            return False
    
    def _create_rabbitmq_properties(self, properties: Dict[str, Any]):
        """Create RabbitMQ message properties."""
        import pika
        
        props = pika.BasicProperties()
        
        # Map common properties
        if 'content_type' in properties:
            props.content_type = properties['content_type']
        if 'correlation_id' in properties:
            props.correlation_id = properties['correlation_id']
        if 'reply_to' in properties:
            props.reply_to = properties['reply_to']
        if 'expiration' in properties:
            props.expiration = properties['expiration']
        if 'message_id' in properties:
            props.message_id = properties['message_id']
        if 'priority' in properties:
            props.priority = properties['priority']
        if 'delivery_mode' in properties:
            props.delivery_mode = properties['delivery_mode']
        if 'headers' in properties:
            props.headers = properties['headers']
        
        return props
    
    def receive_messages(self, queue_name: str, count: int = 1, timeout: int = 5000) -> List[Dict[str, Any]]:
        """
        Receive messages from a queue.
        
        Args:
            queue_name: The queue to receive messages from
            count: Maximum number of messages to receive
            timeout: Timeout in milliseconds
            
        Returns:
            List of received messages as dictionaries
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot receive messages: not connected to {self.mq_type}")
                return []
        
        try:
            messages = []
            
            if self.mq_type == 'rabbitmq':
                if not self.channel:
                    self.channel = self.connection.channel()
                
                # Ensure queue exists
                self.channel.queue_declare(queue=queue_name, passive=True)
                
                # Receive messages
                for _ in range(count):
                    method_frame, properties, body = self.channel.basic_get(queue=queue_name, auto_ack=True)
                    if method_frame:
                        try:
                            message = json.loads(body.decode('utf-8'))
                            messages.append(message)
                        except json.JSONDecodeError:
                            # If not JSON, add raw message
                            messages.append({'raw_message': body.decode('utf-8')})
                    else:
                        # No more messages
                        break
            elif self.mq_type == 'activemq':
                import stomp
                import queue
                
                # Create a queue for receiving messages
                message_queue = queue.Queue()
                
                # Define listener class
                class Listener(stomp.ConnectionListener):
                    def on_message(self, frame):
                        try:
                            message = json.loads(frame.body)
                            message_queue.put(message)
                        except json.JSONDecodeError:
                            message_queue.put({'raw_message': frame.body})
                
                # Register listener
                self.connection.set_listener('', Listener())
                
                # Subscribe to queue
                self.connection.subscribe(destination=f'/queue/{queue_name}', id=1, ack='auto')
                
                # Wait for messages
                start_time = time.time()
                while len(messages) < count and (time.time() - start_time) * 1000 < timeout:
                    try:
                        message = message_queue.get(timeout=(timeout / 1000 - (time.time() - start_time)))
                        messages.append(message)
                    except queue.Empty:
                        break
                
                # Unsubscribe
                self.connection.unsubscribe(id=1)
            elif self.mq_type == 'ibmmq':
                import pymqi
                
                # Create queue object
                queue = pymqi.Queue(self.connection, queue_name)
                
                # Get messages
                for _ in range(count):
                    try:
                        # Get message with timeout
                        message_data = queue.get(wait_interval=timeout)
                        try:
                            message = json.loads(message_data.decode('utf-8'))
                            messages.append(message)
                        except json.JSONDecodeError:
                            messages.append({'raw_message': message_data.decode('utf-8')})
                    except pymqi.MQMIError as e:
                        if e.reason == pymqi.CMQC.MQRC_NO_MSG_AVAILABLE:
                            # No more messages
                            break
                        else:
                            raise
                
                queue.close()
            
            logger.info(f"Received {len(messages)} messages from queue '{queue_name}'")
            return messages
        except Exception as e:
            logger.error(f"Failed to receive messages from queue '{queue_name}': {str(e)}")
            return []
    
    def replay_queue_to_queue(self, source_queue: str, target_queue: str, 
                             filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
                             transform_func: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                             limit: Optional[int] = None) -> int:
        """
        Replay messages from one queue to another, with optional filtering and transformation.
        
        Args:
            source_queue: Source queue to read messages from
            target_queue: Target queue to send messages to
            filter_func: Optional function to filter messages (returns True to include, False to exclude)
            transform_func: Optional function to transform messages before sending
            limit: Optional limit on the number of messages to replay
            
        Returns:
            int: Number of messages successfully replayed
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot replay messages: not connected to {self.mq_type}")
                return 0
        
        try:
            count = 0
            batch_size = 10
            
            while True:
                # Receive a batch of messages
                messages = self.receive_messages(source_queue, count=batch_size, timeout=1000)
                if not messages:
                    break
                
                # Process each message
                for message in messages:
                    # Apply filter if provided
                    if filter_func and not filter_func(message):
                        continue
                    
                    # Apply transformation if provided
                    processed_message = transform_func(message) if transform_func else message
                    
                    # Send to target queue
                    success = self.send_message(target_queue, processed_message)
                    if success:
                        count += 1
                        
                        # Check limit
                        if limit and count >= limit:
                            logger.info(f"Reached limit of {limit} messages replayed")
                            return count
            
            logger.info(f"Replayed {count} messages from '{source_queue}' to '{target_queue}'")
            return count
        except Exception as e:
            logger.error(f"Failed to replay messages from '{source_queue}' to '{target_queue}': {str(e)}")
            return 0
    
    def replay_queue_to_kafka(self, source_queue: str, target_topic: str, 
                             kafka_connector, 
                             filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
                             transform_func: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                             limit: Optional[int] = None) -> int:
        """
        Replay messages from a queue to a Kafka topic.
        
        Args:
            source_queue: Source queue to read messages from
            target_topic: Target Kafka topic to send messages to
            kafka_connector: Instance of KafkaConnector to use for sending messages
            filter_func: Optional function to filter messages (returns True to include, False to exclude)
            transform_func: Optional function to transform messages before sending
            limit: Optional limit on the number of messages to replay
            
        Returns:
            int: Number of messages successfully replayed
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot replay messages: not connected to {self.mq_type}")
                return 0
        
        try:
            # Ensure Kafka connector is connected
            kafka_connected = kafka_connector.connect() if not kafka_connector.producer else True
            if not kafka_connected:
                logger.error(f"Cannot replay messages: Kafka connector not connected")
                return 0
            
            count = 0
            batch_size = 10
            
            while True:
                # Receive a batch of messages
                messages = self.receive_messages(source_queue, count=batch_size, timeout=1000)
                if not messages:
                    break
                
                # Process each message
                for message in messages:
                    # Apply filter if provided
                    if filter_func and not filter_func(message):
                        continue
                    
                    # Apply transformation if provided
                    processed_message = transform_func(message) if transform_func else message
                    
                    # Send to Kafka topic
                    success = kafka_connector.send_message(target_topic, processed_message)
                    if success:
                        count += 1
                        
                        # Check limit
                        if limit and count >= limit:
                            logger.info(f"Reached limit of {limit} messages replayed")
                            return count
            
            logger.info(f"Replayed {count} messages from MQ '{source_queue}' to Kafka topic '{target_topic}'")
            return count
        except Exception as e:
            logger.error(f"Failed to replay messages from MQ '{source_queue}' to Kafka topic '{target_topic}': {str(e)}")
            return 0
    
    def delete_queue(self, queue_name: str) -> bool:
        """
        Delete a queue.
        
        Args:
            queue_name: Name of the queue to delete
            
        Returns:
            bool: True if queue deleted successfully, False otherwise
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot delete queue: not connected to {self.mq_type}")
                return False
        
        try:
            if self.mq_type == 'rabbitmq':
                if not self.channel:
                    self.channel = self.connection.channel()
                
                # Delete queue
                self.channel.queue_delete(queue=queue_name)
            elif self.mq_type == 'activemq':
                # For ActiveMQ, queues are typically managed via JMX or the ActiveMQ admin console
                logger.warning(f"Queue deletion not directly supported for ActiveMQ. Use the admin console.")
                return False
            elif self.mq_type == 'ibmmq':
                # For IBM MQ, queues are typically defined by an administrator
                logger.warning(f"Queue deletion not directly supported for IBM MQ. Use the MQ administration tools.")
                return False
            
            logger.info(f"Queue '{queue_name}' deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete queue '{queue_name}': {str(e)}")
            return False