
import logging
import json
from typing import Dict, List, Optional, Any, Union, Tuple
import time

# Create a logger for this module
logger = logging.getLogger(__name__)

class DBConnector:
    """
    Connector for interacting with various database systems (supports PostgreSQL, MySQL, Oracle, SQLite).
    Provides methods for executing queries, updating data, and handling transactions.
    """
    
    # Supported database types
    SUPPORTED_TYPES = ['postgresql', 'mysql', 'oracle', 'sqlite', 'sqlserver']
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DB connector with the given configuration.
        
        Args:
            config: A dictionary containing database configuration parameters:
                - db_type: Type of database ('postgresql', 'mysql', 'oracle', 'sqlite', 'sqlserver')
                - host: Database server hostname (not required for SQLite)
                - port: Database server port (not required for SQLite)
                - database: Database name (or file path for SQLite)
                - username: Username for authentication (not required for SQLite)
                - password: Password for authentication (not required for SQLite)
                - connection_options: Additional connection options
        """
        self.config = config
        self.db_type = config.get('db_type', 'postgresql').lower()
        
        if self.db_type not in self.SUPPORTED_TYPES:
            logger.warning(f"Unsupported database type: {self.db_type}. Defaulting to PostgreSQL.")
            self.db_type = 'postgresql'
        
        # Common configuration
        self.host = config.get('host', 'localhost' if self.db_type != 'sqlite' else None)
        self.port = config.get('port', self._get_default_port())
        self.database = config.get('database', '')
        self.username = config.get('username', '' if self.db_type != 'sqlite' else None)
        self.password = config.get('password', '' if self.db_type != 'sqlite' else None)
        self.connection_options = config.get('connection_options', {})
        
        # Connection object
        self.connection = None
        self.cursor = None
        
        logger.info(f"Initialized {self.db_type} connector" + 
                  (f" for database '{self.database}' on host '{self.host}'" if self.db_type != 'sqlite' else f" for database '{self.database}'"))
    
    def _get_default_port(self) -> Optional[int]:
        """Get the default port for the selected database type."""
        if self.db_type == 'postgresql':
            return 5432
        elif self.db_type == 'mysql':
            return 3306
        elif self.db_type == 'oracle':
            return 1521
        elif self.db_type == 'sqlserver':
            return 1433
        elif self.db_type == 'sqlite':
            return None
        return None
    
    def connect(self) -> bool:
        """
        Establish connection to the database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.db_type == 'postgresql':
                return self._connect_postgresql()
            elif self.db_type == 'mysql':
                return self._connect_mysql()
            elif self.db_type == 'oracle':
                return self._connect_oracle()
            elif self.db_type == 'sqlite':
                return self._connect_sqlite()
            elif self.db_type == 'sqlserver':
                return self._connect_sqlserver()
            else:
                logger.error(f"Unsupported database type: {self.db_type}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to {self.db_type}: {str(e)}")
            return False
    
    def _connect_postgresql(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            import psycopg2
            import psycopg2.extras
            
            # Create connection
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                **self.connection_options
            )
            
            # Create cursor with dictionary factory
            self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            logger.info(f"Successfully connected to PostgreSQL database '{self.database}' on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL database: {str(e)}")
            return False
    
    def _connect_mysql(self) -> bool:
        """Connect to MySQL/MariaDB database."""
        try:
            import mysql.connector
            
            # Create connection
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                **self.connection_options
            )
            
            # Create cursor
            self.cursor = self.connection.cursor(dictionary=True)
            
            logger.info(f"Successfully connected to MySQL database '{self.database}' on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MySQL database: {str(e)}")
            return False
    
    def _connect_oracle(self) -> bool:
        """Connect to Oracle database."""
        try:
            import cx_Oracle
            
            # Create connection string
            connection_string = f"{self.username}/{self.password}@{self.host}:{self.port}/{self.database}"
            
            # Create connection
            self.connection = cx_Oracle.connect(connection_string)
            
            # Create cursor
            self.cursor = self.connection.cursor()
            
            logger.info(f"Successfully connected to Oracle database '{self.database}' on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Oracle database: {str(e)}")
            return False
    
    def _connect_sqlite(self) -> bool:
        """Connect to SQLite database."""
        try:
            import sqlite3
            
            # Create connection
            self.connection = sqlite3.connect(self.database)
            
            # Configure connection to return dictionaries
            self.connection.row_factory = sqlite3.Row
            
            # Create cursor
            self.cursor = self.connection.cursor()
            
            logger.info(f"Successfully connected to SQLite database '{self.database}'")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {str(e)}")
            return False
    
    def _connect_sqlserver(self) -> bool:
        """Connect to SQL Server database."""
        try:
            import pyodbc
            
            # Create connection string
            connection_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={self.host},{self.port};DATABASE={self.database};UID={self.username};PWD={self.password}"
            
            # Add additional connection options
            for key, value in self.connection_options.items():
                connection_string += f";{key}={value}"
            
            # Create connection
            self.connection = pyodbc.connect(connection_string)
            
            # Create cursor
            self.cursor = self.connection.cursor()
            
            logger.info(f"Successfully connected to SQL Server database '{self.database}' on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SQL Server database: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Close connection to the database."""
        try:
            if self.cursor:
                self.cursor.close()
            
            if self.connection:
                self.connection.close()
            
            self.connection = None
            self.cursor = None
            
            logger.info(f"Disconnected from {self.db_type} database")
        except Exception as e:
            logger.error(f"Error while disconnecting from {self.db_type} database: {str(e)}")
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return the results.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot execute query: not connected to {self.db_type} database")
                return []
        
        try:
            # Execute query
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # Fetch results
            if self.db_type == 'postgresql' or self.db_type == 'mysql':
                # These cursor factories return dictionaries directly
                results = self.cursor.fetchall()
            elif self.db_type == 'sqlite':
                # SQLite's row_factory returns Row objects that can be used as dictionaries
                rows = self.cursor.fetchall()
                results = [dict(row) for row in rows]
            else:
                # For other databases, convert to dictionaries manually
                column_names = [desc[0] for desc in self.cursor.description]
                rows = self.cursor.fetchall()
                results = []
                for row in rows:
                    result = {}
                    for i, value in enumerate(row):
                        result[column_names[i]] = value
                    results.append(result)
            
            logger.info(f"Query executed successfully, returned {len(results)} rows")
            return results
        except Exception as e:
            logger.error(f"Failed to execute query: {str(e)}")
            return []
    
    def execute_update(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        Execute an UPDATE, INSERT, or DELETE query and return the number of affected rows.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot execute update: not connected to {self.db_type} database")
                return 0
        
        try:
            # Execute query
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # Commit changes
            self.connection.commit()
            
            # Get row count
            rows_affected = self.cursor.rowcount
            
            logger.info(f"Update executed successfully, affected {rows_affected} rows")
            return rows_affected
        except Exception as e:
            # Rollback on error
            self.connection.rollback()
            logger.error(f"Failed to execute update: {str(e)}")
            return 0
    
    def execute_batch(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """
        Execute a batch of updates with different parameters.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter dictionaries
            
        Returns:
            Number of affected rows
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot execute batch: not connected to {self.db_type} database")
                return 0
        
        try:
            total_affected = 0
            
            # Start transaction
            self.connection.begin()
            
            # Execute each query with parameters
            for params in params_list:
                self.cursor.execute(query, params)
                total_affected += self.cursor.rowcount
            
            # Commit transaction
            self.connection.commit()
            
            logger.info(f"Batch executed successfully, affected {total_affected} rows")
            return total_affected
        except Exception as e:
            # Rollback on error
            self.connection.rollback()
            logger.error(f"Failed to execute batch: {str(e)}")
            return 0
    
    def begin_transaction(self) -> bool:
        """
        Begin a new transaction.
        
        Returns:
            bool: True if transaction started successfully, False otherwise
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot begin transaction: not connected to {self.db_type} database")
                return False
        
        try:
            if self.db_type == 'postgresql' or self.db_type == 'mysql' or self.db_type == 'oracle' or self.db_type == 'sqlserver':
                # Most database drivers handle this similarly
                self.connection.begin()
            elif self.db_type == 'sqlite':
                # For SQLite, execute BEGIN statement
                self.cursor.execute("BEGIN")
            
            logger.info("Transaction started")
            return True
        except Exception as e:
            logger.error(f"Failed to begin transaction: {str(e)}")
            return False
    
    def commit_transaction(self) -> bool:
        """
        Commit the current transaction.
        
        Returns:
            bool: True if transaction committed successfully, False otherwise
        """
        if not self.connection:
            logger.error(f"Cannot commit transaction: not connected to {self.db_type} database")
            return False
        
        try:
            self.connection.commit()
            logger.info("Transaction committed")
            return True
        except Exception as e:
            logger.error(f"Failed to commit transaction: {str(e)}")
            return False
    
    def rollback_transaction(self) -> bool:
        """
        Rollback the current transaction.
        
        Returns:
            bool: True if transaction rolled back successfully, False otherwise
        """
        if not self.connection:
            logger.error(f"Cannot rollback transaction: not connected to {self.db_type} database")
            return False
        
        try:
            self.connection.rollback()
            logger.info("Transaction rolled back")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback transaction: {str(e)}")
            return False
    
    def execute_script(self, script: str) -> bool:
        """
        Execute a SQL script containing multiple statements.
        
        Args:
            script: SQL script to execute
            
        Returns:
            bool: True if script executed successfully, False otherwise
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot execute script: not connected to {self.db_type} database")
                return False
        
        try:
            # For most databases, the script needs to be split into statements
            if self.db_type == 'postgresql':
                # PostgreSQL can execute the entire script in one go
                self.cursor.execute(script)
                self.connection.commit()
            elif self.db_type == 'sqlite':
                # SQLite can execute scripts using executescript
                self.cursor.executescript(script)
                self.connection.commit()
            else:
                # For other databases, split the script into statements and execute each one
                statements = script.split(';')
                for statement in statements:
                    if statement.strip():
                        self.cursor.execute(statement)
                self.connection.commit()
            
            logger.info("Script executed successfully")
            return True
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to execute script: {str(e)}")
            return False
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            bool: True if table exists, False otherwise
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot check table existence: not connected to {self.db_type} database")
                return False
        
        try:
            if self.db_type == 'postgresql':
                query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
                """
                self.cursor.execute(query, (table_name,))
                return self.cursor.fetchone()[0]
            elif self.db_type == 'mysql':
                query = """
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s;
                """
                self.cursor.execute(query, (self.database, table_name))
                return self.cursor.fetchone()['COUNT(*)'] > 0
            elif self.db_type == 'oracle':
                query = """
                SELECT COUNT(*) 
                FROM user_tables 
                WHERE table_name = UPPER(:table_name);
                """
                self.cursor.execute(query, {'table_name': table_name})
                count = self.cursor.fetchone()[0]
                return count > 0
            elif self.db_type == 'sqlite':
                query = """
                SELECT COUNT(*) 
                FROM sqlite_master 
                WHERE type='table' AND name=?;
                """
                self.cursor.execute(query, (table_name,))
                count = self.cursor.fetchone()[0]
                return count > 0
            elif self.db_type == 'sqlserver':
                query = """
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = ?;
                """
                self.cursor.execute(query, (table_name,))
                count = self.cursor.fetchone()[0]
                return count > 0
            
            return False
        except Exception as e:
            logger.error(f"Failed to check if table '{table_name}' exists: {str(e)}")
            return False
    
    def export_query_to_kafka(self, query: str, params: Optional[Dict[str, Any]], 
                             kafka_connector, topic: str,
                             transform_func=None, batch_size: int = 1000) -> int:
        """
        Execute a query and send the results to a Kafka topic.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            kafka_connector: Instance of KafkaConnector to use for sending messages
            topic: Kafka topic to send messages to
            transform_func: Optional function to transform rows before sending
            batch_size: Number of rows to fetch and process at once
            
        Returns:
            Number of rows sent to Kafka
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot export to Kafka: not connected to {self.db_type} database")
                return 0
        
        try:
            # Ensure Kafka connector is connected
            kafka_connected = kafka_connector.connect() if not kafka_connector.producer else True
            if not kafka_connected:
                logger.error(f"Cannot export to Kafka: Kafka connector not connected")
                return 0
            
            # Execute query with server-side cursor for large result sets
            if self.db_type == 'postgresql':
                # For PostgreSQL, use named cursor for server-side cursor
                server_cursor = self.connection.cursor(name='export_cursor')
                if params:
                    server_cursor.execute(query, params)
                else:
                    server_cursor.execute(query)
                
                # Get column names
                column_names = [desc[0] for desc in server_cursor.description]
                
                # Process in batches
                count = 0
                while True:
                    rows = server_cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    
                    # Convert rows to dictionaries
                    for row in rows:
                        # Create message
                        message = {}
                        for i, col_name in enumerate(column_names):
                            message[col_name] = row[i]
                        
                        # Apply transformation if provided
                        if transform_func:
                            message = transform_func(message)
                        
                        # Send to Kafka
                        kafka_connector.send_message(topic, message)
                        count += 1
                
                # Close cursor
                server_cursor.close()
            else:
                # For other databases, fetch all rows (could be memory-intensive for large results)
                results = self.execute_query(query, params)
                count = 0
                
                for row in results:
                    # Apply transformation if provided
                    if transform_func:
                        row = transform_func(row)
                    
                    # Send to Kafka
                    kafka_connector.send_message(topic, row)
                    count += 1
            
            logger.info(f"Exported {count} rows to Kafka topic '{topic}'")
            return count
        except Exception as e:
            logger.error(f"Failed to export query results to Kafka: {str(e)}")
            return 0
    
    def export_query_to_mq(self, query: str, params: Optional[Dict[str, Any]], 
                         mq_connector, queue_name: str,
                         transform_func=None, batch_size: int = 1000) -> int:
        """
        Execute a query and send the results to a message queue.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            mq_connector: Instance of MQConnector to use for sending messages
            queue_name: Queue name to send messages to
            transform_func: Optional function to transform rows before sending
            batch_size: Number of rows to fetch and process at once
            
        Returns:
            Number of rows sent to the queue
        """
        if not self.connection:
            connected = self.connect()
            if not connected:
                logger.error(f"Cannot export to MQ: not connected to {self.db_type} database")
                return 0
        
        try:
            # Ensure MQ connector is connected
            mq_connected = mq_connector.connect() if not mq_connector.connection else True
            if not mq_connected:
                logger.error(f"Cannot export to MQ: MQ connector not connected")
                return 0
            
            # Execute query
            results = self.execute_query(query, params)
            count = 0
            
            # Process results
            for row in results:
                # Apply transformation if provided
                if transform_func:
                    row = transform_func(row)
                
                # Send to MQ
                mq_connector.send_message(queue_name, row)
                count += 1
            
            logger.info(f"Exported {count} rows to MQ queue '{queue_name}'")
            return count
        except Exception as e:
            logger.error(f"Failed to export query results to MQ: {str(e)}")
            return 0