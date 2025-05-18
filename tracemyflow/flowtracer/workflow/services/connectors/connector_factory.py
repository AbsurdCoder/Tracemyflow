import logging
from typing import Dict, Any, Optional, Union

from .kafka_connector import KafkaConnector
from .mq_connector import MQConnector
from .db_connector import DBConnector

# Create a logger for this module
logger = logging.getLogger(__name__)

class ConnectorFactory:
    """
    Factory for creating the appropriate connector based on the configuration.
    """
    
    @staticmethod
    def create_connector(connector_type: str, config: Dict[str, Any]) -> Optional[Union[KafkaConnector, MQConnector, DBConnector]]:
        """
        Create and return a connector instance based on the specified type and configuration.
        
        Args:
            connector_type: Type of connector to create ('kafka', 'mq', or 'db')
            config: Configuration for the connector
            
        Returns:
            Instance of the appropriate connector or None if type is not supported
        """
        try:
            if connector_type.lower() == 'kafka':
                return KafkaConnector(config)
            elif connector_type.lower() == 'mq':
                return MQConnector(config)
            elif connector_type.lower() == 'db':
                return DBConnector(config)
            else:
                logger.error(f"Unsupported connector type: {connector_type}")
                return None
        except Exception as e:
            logger.error(f"Failed to create connector of type '{connector_type}': {str(e)}")
            return None
    
    @staticmethod
    def create_kafka_connector(config: Dict[str, Any]) -> Optional[KafkaConnector]:
        """Create and return a Kafka connector instance."""
        return ConnectorFactory.create_connector('kafka', config)
    
    @staticmethod
    def create_mq_connector(config: Dict[str, Any]) -> Optional[MQConnector]:
        """Create and return an MQ connector instance."""
        return ConnectorFactory.create_connector('mq', config)
    
    @staticmethod
    def create_db_connector(config: Dict[str, Any]) -> Optional[DBConnector]:
        """Create and return a DB connector instance."""
        return ConnectorFactory.create_connector('db', config)