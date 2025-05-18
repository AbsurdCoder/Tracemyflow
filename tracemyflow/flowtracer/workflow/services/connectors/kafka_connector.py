
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Callable

# Create a logger for this module
logger = logging.getLogger(__name__)

class KafkaConnector:
    """
    Connector for interacting with Kafka topics.
    Provides methods for producing messages to and consuming messages from Kafka topics.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Kafka connector with the given configuration.
        
        Args:
            config: A dictionary containing Kafka configuration parameters:
                - bootstrap_servers: List of Kafka bootstrap servers
                - group_id: Consumer group ID (for consumption)
                - auto_offset_reset: Offset reset strategy ('earliest' or 'latest')
                - security_protocol: Security protocol (optional)
                - sasl_mechanism: SASL mechanism (optional)
                - sasl_plain_username: SASL username (optional)
                - sasl_plain_password: SASL password (optional)
        """
        self.config = config
        self.bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')
        self.group_id = config.get('group_id', 'default-group')
        self.auto_offset_reset = config.get('auto_offset_reset', 'earliest')
        
        # Security configurations
        self.security_protocol = config.get('security_protocol', None)
        self.sasl_mechanism = config.get('sasl_mechanism', None)
        self.sasl_plain_username = config.get('sasl_plain_username', None)
        self.sasl_plain_password = config.get('sasl_plain_password', None)
        
        # Producer and consumer instances
        self.producer = None
        self.consumer = None
        
        logger.info(f"Initialized Kafka connector with bootstrap servers: {self.bootstrap_servers}")
    
    def connect(self) -> bool:
        """
        Establish connection to Kafka.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Import kafka library here to avoid dependency if not used
            from kafka import KafkaProducer, KafkaConsumer
            
            # Create producer config
            producer_config = {
                'bootstrap_servers': self.bootstrap_servers,
                'value_serializer': lambda x: json.dumps(x).encode('utf-8')
            }
            
            # Add security configurations if provided
            if self.security_protocol:
                producer_config['security_protocol'] = self.security_protocol
            if self.sasl_mechanism:
                producer_config['sasl_mechanism'] = self.sasl_mechanism
            if self.sasl_plain_username and self.sasl_plain_password:
                producer_config['sasl_plain_username'] = self.sasl_plain_username
                producer_config['sasl_plain_password'] = self.sasl_plain_password
            
            # Create producer
            self.producer = KafkaProducer(**producer_config)
            
            # Create consumer config
            consumer_config = {
                'bootstrap_servers': self.bootstrap_servers,
                'group_id': self.group_id,
                'auto_offset_reset': self.auto_offset_reset,
                'value_deserializer': lambda x: json.loads(x.decode('utf-8'))
            }
            
            # Add security configurations if provided
            if self.security_protocol:
                consumer_config['security_protocol'] = self.security_protocol
            if self.sasl_mechanism:
                consumer_config['sasl_mechanism'] = self.sasl_mechanism
            if self.sasl_plain_username and self.sasl_plain_password:
                consumer_config['sasl_plain_username'] = self.sasl_plain_username
                consumer_config['sasl_plain_password'] = self.sasl_plain_password
            
            # Create consumer (without subscribing to any topic yet)
            self.consumer = KafkaConsumer(**consumer_config)
            
            logger.info("Successfully connected to Kafka")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Close all connections to Kafka."""
        try:
            if self.producer:
                self.producer.close()
                self.producer = None
            
            if self.consumer:
                self.consumer.close()
                self.consumer = None
            
            logger.info("Disconnected from Kafka")
        except Exception as e:
            logger.error(f"Error while disconnecting from Kafka: {str(e)}")
    
    def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """
        Send a message to a Kafka topic.
        
        Args:
            topic: The topic to send the message to
            message: The message payload as a dictionary
            key: Optional message key
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        if not self.producer:
            connected = self.connect()
            if not connected:
                logger.error("Cannot send message: not connected to Kafka")
                return False
        
        try:
            # Encode key if provided
            encoded_key = key.encode('utf-8') if key else None
            
            # Send message
            future = self.producer.send(topic, value=message, key=encoded_key)
            # Wait for message to be sent
            future.get(timeout=10)
            
            logger.info(f"Message sent to topic '{topic}' successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to topic '{topic}': {str(e)}")
            return False
    
    def consume_messages(self, topic: str, timeout_ms: int = 1000, max_records: int = 100) -> List[Dict[str, Any]]:
        """
        Consume messages from a Kafka topic.
        
        Args:
            topic: The topic to consume messages from
            timeout_ms: Maximum time to wait for messages in milliseconds
            max_records: Maximum number of records to consume
            
        Returns:
            List of consumed messages as dictionaries
        """
        if not self.consumer:
            connected = self.connect()
            if not connected:
                logger.error("Cannot consume messages: not connected to Kafka")
                return []
        
        try:
            # Subscribe to topic
            self.consumer.subscribe([topic])
            
            # Poll for messages
            messages = []
            records = self.consumer.poll(timeout_ms=timeout_ms, max_records=max_records)
            
            for topic_partition, partition_records in records.items():
                for record in partition_records:
                    messages.append(record.value)
            
            logger.info(f"Consumed {len(messages)} messages from topic '{topic}'")
            return messages
        except Exception as e:
            logger.error(f"Failed to consume messages from topic '{topic}': {str(e)}")
            return []
    
    def replay_topic_to_topic(self, source_topic: str, target_topic: str, 
                             filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
                             transform_func: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                             limit: Optional[int] = None) -> int:
        """
        Replay messages from one Kafka topic to another, with optional filtering and transformation.
        
        Args:
            source_topic: Source topic to read messages from
            target_topic: Target topic to send messages to
            filter_func: Optional function to filter messages (returns True to include, False to exclude)
            transform_func: Optional function to transform messages before sending
            limit: Optional limit on the number of messages to replay
            
        Returns:
            int: Number of messages successfully replayed
        """
        if not self.consumer or not self.producer:
            connected = self.connect()
            if not connected:
                logger.error("Cannot replay messages: not connected to Kafka")
                return 0
        
        try:
            # Subscribe to source topic
            self.consumer.subscribe([source_topic])
            
            # Poll for messages
            count = 0
            # Reset offsets to beginning of topic
            self.consumer.seek_to_beginning()
            
            while True:
                records = self.consumer.poll(timeout_ms=1000, max_records=100)
                if not records:
                    break
                
                for topic_partition, partition_records in records.items():
                    for record in partition_records:
                        # Apply filter if provided
                        if filter_func and not filter_func(record.value):
                            continue
                        
                        # Apply transformation if provided
                        message = transform_func(record.value) if transform_func else record.value
                        
                        # Send to target topic
                        self.producer.send(target_topic, value=message, key=record.key)
                        count += 1
                        
                        # Check limit
                        if limit and count >= limit:
                            logger.info(f"Reached limit of {limit} messages replayed")
                            self.producer.flush()
                            return count
            
            # Flush producer to ensure all messages are sent
            self.producer.flush()
            logger.info(f"Replayed {count} messages from '{source_topic}' to '{target_topic}'")
            return count
        except Exception as e:
            logger.error(f"Failed to replay messages from '{source_topic}' to '{target_topic}': {str(e)}")
            return 0
    
    def create_topic(self, topic: str, num_partitions: int = 1, replication_factor: int = 1) -> bool:
        """
        Create a new Kafka topic.
        
        Args:
            topic: Name of the topic to create
            num_partitions: Number of partitions for the topic
            replication_factor: Replication factor for the topic
            
        Returns:
            bool: True if topic created successfully, False otherwise
        """
        try:
            # Import kafka-admin library
            from kafka.admin import KafkaAdminClient, NewTopic
            
            # Create admin client
            admin_config = {
                'bootstrap_servers': self.bootstrap_servers
            }
            
            # Add security configurations if provided
            if self.security_protocol:
                admin_config['security_protocol'] = self.security_protocol
            if self.sasl_mechanism:
                admin_config['sasl_mechanism'] = self.sasl_mechanism
            if self.sasl_plain_username and self.sasl_plain_password:
                admin_config['sasl_plain_username'] = self.sasl_plain_username
                admin_config['sasl_plain_password'] = self.sasl_plain_password
            
            admin_client = KafkaAdminClient(**admin_config)
            
            # Create topic
            topic_list = [NewTopic(name=topic, num_partitions=num_partitions, replication_factor=replication_factor)]
            admin_client.create_topics(new_topics=topic_list, validate_only=False)
            
            admin_client.close()
            logger.info(f"Created Kafka topic '{topic}' with {num_partitions} partitions and replication factor {replication_factor}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Kafka topic '{topic}': {str(e)}")
            return False
    
    def delete_topic(self, topic: str) -> bool:
        """
        Delete a Kafka topic.
        
        Args:
            topic: Name of the topic to delete
            
        Returns:
            bool: True if topic deleted successfully, False otherwise
        """
        try:
            # Import kafka-admin library
            from kafka.admin import KafkaAdminClient
            
            # Create admin client
            admin_config = {
                'bootstrap_servers': self.bootstrap_servers
            }
            
            # Add security configurations if provided
            if self.security_protocol:
                admin_config['security_protocol'] = self.security_protocol
            if self.sasl_mechanism:
                admin_config['sasl_mechanism'] = self.sasl_mechanism
            if self.sasl_plain_username and self.sasl_plain_password:
                admin_config['sasl_plain_username'] = self.sasl_plain_username
                admin_config['sasl_plain_password'] = self.sasl_plain_password
            
            admin_client = KafkaAdminClient(**admin_config)
            
            # Delete topic
            admin_client.delete_topics([topic])
            
            admin_client.close()
            logger.info(f"Deleted Kafka topic '{topic}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Kafka topic '{topic}': {str(e)}")
            return False