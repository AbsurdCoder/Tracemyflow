# workflow/services/workflow_executor.py

import yaml
import time
import logging
from datetime import datetime
from django.utils import timezone
from ..models import (
    WorkflowDefinition, 
    WorkflowExecution, 
    WorkflowComponent, 
    ComponentExecutionStatus,
    RetryStrategy
)

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    def __init__(self, workflow_execution_id):
        self.execution = WorkflowExecution.objects.get(pk=workflow_execution_id)
        self.workflow = self.execution.workflow
        self.validation_enabled = self.execution.validation_enabled
        self.components = WorkflowComponent.objects.filter(workflow=self.workflow).order_by('order')
        
    def execute(self):
        """Execute the workflow"""
        self.execution.status = 'running'
        self.execution.save()
        
        log_message = f"Starting workflow execution: {self.workflow.name} (ID: {self.execution.id})"
        self._log(log_message)
        
        try:
            # Create component execution status records
            self._initialize_component_statuses()
            
            # Execute each component in order
            for component in self.components:
                component_status = ComponentExecutionStatus.objects.get(
                    workflow_execution=self.execution, 
                    component=component
                )
                
                self._execute_component(component, component_status)
                
            # Check if all components completed successfully
            all_completed = self._check_all_components_completed()
            
            if all_completed:
                self.execution.status = 'completed'
                log_message = f"Workflow execution completed successfully: {self.workflow.name}"
            else:
                self.execution.status = 'partially_completed'
                log_message = f"Workflow execution partially completed: {self.workflow.name}"
            
            self._log(log_message)
            
        except Exception as e:
            self.execution.status = 'failed'
            error_message = f"Workflow execution failed: {str(e)}"
            self._log(error_message)
            logger.exception(error_message)
        
        self.execution.completed_at = timezone.now()
        self.execution.save()
        
        return self.execution.status
    
    def _initialize_component_statuses(self):
        """Initialize status records for all components"""
        for component in self.components:
            ComponentExecutionStatus.objects.create(
                workflow_execution=self.execution,
                component=component,
                status='pending'
            )
    
    def _execute_component(self, component, component_status):
        """Execute a single component with retry logic"""
        component_status.status = 'running'
        component_status.started_at = timezone.now()
        component_status.save()
        
        log_message = f"Executing component: {component.name} (Type: {component.component_type})"
        self._log(log_message)
        
        retry_strategies = RetryStrategy.objects.filter(component=component)
        max_retries = 0
        current_retry = 0
        delay_seconds = 0
        
        if retry_strategies.exists():
            strategy = retry_strategies.first()
            max_retries = strategy.max_retries
            delay_seconds = strategy.initial_delay_seconds
        
        success = False
        
        while not success and current_retry <= max_retries:
            try:
                # Here we would implement the actual execution logic for each component type
                # For now, we'll just simulate execution
                
                if component.component_type == 'kafka':
                    self._simulate_kafka_component(component)
                elif component.component_type == 'mq':
                    self._simulate_mq_component(component)
                elif component.component_type == 'db':
                    self._simulate_db_component(component)
                elif component.component_type == 'service':
                    self._simulate_service_component(component)
                elif component.component_type == 'api':
                    self._simulate_api_component(component)
                
                # If we reach here, execution was successful
                success = True
                component_status.status = 'completed'
                log_message = f"Component executed successfully: {component.name}"
                self._log(log_message)
                
            except Exception as e:
                current_retry += 1
                component_status.retry_count = current_retry
                
                if current_retry <= max_retries:
                    log_message = f"Component execution failed, retrying ({current_retry}/{max_retries}): {component.name}, Error: {str(e)}"
                    self._log(log_message)
                    
                    # Calculate delay for next retry if using exponential backoff
                    if retry_strategies.exists() and retry_strategies.first().strategy_type == 'exponential':
                        backoff_factor = retry_strategies.first().backoff_factor
                        delay_seconds = delay_seconds * backoff_factor
                    
                    # Wait before retry
                    time.sleep(delay_seconds)
                else:
                    component_status.status = 'failed'
                    component_status.error_message = str(e)
                    log_message = f"Component execution failed after {max_retries} retries: {component.name}, Error: {str(e)}"
                    self._log(log_message)
                    
                    # If validation is required, fail the entire workflow
                    if self.validation_enabled and self.workflow.validation_mode == 'required':
                        raise Exception(f"Component {component.name} failed and validation is required")
        
        component_status.completed_at = timezone.now()
        component_status.save()
    
    def _check_all_components_completed(self):
        """Check if all components completed successfully"""
        statuses = ComponentExecutionStatus.objects.filter(workflow_execution=self.execution)
        return all(status.status == 'completed' for status in statuses)
    
    def _log(self, message):
        """Add a log message to the execution log"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        self.execution.execution_log += log_entry
        self.execution.save(update_fields=['execution_log'])
        
        logger.info(message)
    
    # Simulation methods for different component types
    def _simulate_kafka_component(self, component):
        """Simulate execution of a Kafka component"""
        time.sleep(0.5)  # Simulate processing time
        
        # Here we would implement Kafka specific logic using your kafka connector
        # For now, we'll just log that we're simulating execution
        self._log(f"Simulating Kafka component execution: {component.name}")
        
        # Randomly fail to test retry logic (not for production)
        # import random
        # if random.random() < 0.3:  # 30% chance of failure
        #     raise Exception("Simulated Kafka error")
    
    def _simulate_mq_component(self, component):
        """Simulate execution of a Message Queue component"""
        time.sleep(0.5)  # Simulate processing time
        self._log(f"Simulating MQ component execution: {component.name}")
    
    def _simulate_db_component(self, component):
        """Simulate execution of a Database component"""
        time.sleep(0.7)  # Simulate processing time
        self._log(f"Simulating DB component execution: {component.name}")
    
    def _simulate_service_component(self, component):
        """Simulate execution of a Service component"""
        time.sleep(0.3)  # Simulate processing time
        self._log(f"Simulating Service component execution: {component.name}")
    
    def _simulate_api_component(self, component):
        """Simulate execution of an API component"""
        time.sleep(0.4)  # Simulate processing time
        self._log(f"Simulating API component execution: {component.name}")
        
    def execute_sub_workflow(self, component_id):
        """Execute a specific component and its dependencies as a sub-workflow"""
        component = WorkflowComponent.objects.get(pk=component_id)
        
        # Create a component status if it doesn't exist
        component_status, created = ComponentExecutionStatus.objects.get_or_create(
            workflow_execution=self.execution,
            component=component,
            defaults={'status': 'pending'}
        )
        
        # Execute just this component
        self._execute_component(component, component_status)
        
        return component_status.status


    def _simulate_kafka_component(self, component):
        """Execute a Kafka component using the KafkaConnector."""
        try:
            from .connectors.connector_factory import ConnectorFactory
            
            # Get component configuration
            config = component.config
            
            # Create Kafka connector
            kafka_connector = ConnectorFactory.create_kafka_connector(config)
            if not kafka_connector:
                raise Exception(f"Failed to create Kafka connector for component {component.name}")
            
            # Connect to Kafka
            connected = kafka_connector.connect()
            if not connected:
                raise Exception(f"Failed to connect to Kafka for component {component.name}")
            
            # Get operation type from component configuration
            operation_type = config.get('operation_type', 'consume')
            
            if operation_type == 'produce':
                # Produce message to topic
                topic = config.get('topic')
                message = config.get('message', {})
                
                if not topic:
                    raise Exception(f"No topic specified for Kafka producer component {component.name}")
                
                success = kafka_connector.send_message(topic, message)
                if not success:
                    raise Exception(f"Failed to send message to Kafka topic {topic}")
                
                self._log(f"Produced message to Kafka topic {topic}")
            
            elif operation_type == 'consume':
                # Consume messages from topic
                topic = config.get('topic')
                max_messages = config.get('max_messages', 10)
                timeout_ms = config.get('timeout_ms', 5000)
                
                if not topic:
                    raise Exception(f"No topic specified for Kafka consumer component {component.name}")
                
                messages = kafka_connector.consume_messages(topic, timeout_ms=timeout_ms, max_records=max_messages)
                self._log(f"Consumed {len(messages)} messages from Kafka topic {topic}")
            
            elif operation_type == 'replay':
                # Replay messages from one topic to another
                source_topic = config.get('source_topic')
                target_topic = config.get('target_topic')
                limit = config.get('limit')
                
                if not source_topic or not target_topic:
                    raise Exception(f"Source or target topic not specified for Kafka replay component {component.name}")
                
                count = kafka_connector.replay_topic_to_topic(
                    source_topic=source_topic,
                    target_topic=target_topic,
                    limit=limit
                )
                
                self._log(f"Replayed {count} messages from Kafka topic {source_topic} to {target_topic}")
            
            else:
                raise Exception(f"Unsupported Kafka operation type: {operation_type}")
            
            # Disconnect from Kafka
            kafka_connector.disconnect()
            
        except Exception as e:
            self._log(f"Error executing Kafka component {component.name}: {str(e)}")
            raise

    def _simulate_mq_component(self, component):
        """Execute an MQ component using the MQConnector."""
        try:
            from .connectors.connector_factory import ConnectorFactory
            
            # Get component configuration
            config = component.config
            
            # Create MQ connector
            mq_connector = ConnectorFactory.create_mq_connector(config)
            if not mq_connector:
                raise Exception(f"Failed to create MQ connector for component {component.name}")
            
            # Connect to MQ
            connected = mq_connector.connect()
            if not connected:
                raise Exception(f"Failed to connect to MQ for component {component.name}")
            
            # Get operation type from component configuration
            operation_type = config.get('operation_type', 'receive')
            
            if operation_type == 'send':
                # Send message to queue
                queue_name = config.get('queue_name')
                message = config.get('message', {})
                properties = config.get('properties')
                
                if not queue_name:
                    raise Exception(f"No queue specified for MQ sender component {component.name}")
                
                # Declare queue if needed
                if config.get('declare_queue', True):
                    mq_connector.declare_queue(queue_name)
                
                success = mq_connector.send_message(queue_name, message, properties)
                if not success:
                    raise Exception(f"Failed to send message to MQ queue {queue_name}")
                
                self._log(f"Sent message to MQ queue {queue_name}")
            
            elif operation_type == 'receive':
                # Receive messages from queue
                queue_name = config.get('queue_name')
                count = config.get('count', 1)
                timeout = config.get('timeout', 5000)
                
                if not queue_name:
                    raise Exception(f"No queue specified for MQ receiver component {component.name}")
                
                messages = mq_connector.receive_messages(queue_name, count=count, timeout=timeout)
                self._log(f"Received {len(messages)} messages from MQ queue {queue_name}")
            
            elif operation_type == 'replay_queue_to_queue':
                # Replay messages from one queue to another
                source_queue = config.get('source_queue')
                target_queue = config.get('target_queue')
                limit = config.get('limit')
                
                if not source_queue or not target_queue:
                    raise Exception(f"Source or target queue not specified for MQ replay component {component.name}")
                
                count = mq_connector.replay_queue_to_queue(
                    source_queue=source_queue,
                    target_queue=target_queue,
                    limit=limit
                )
                
                self._log(f"Replayed {count} messages from MQ queue {source_queue} to {target_queue}")
            
            elif operation_type == 'replay_queue_to_kafka':
                # Replay messages from queue to Kafka topic
                source_queue = config.get('source_queue')
                target_topic = config.get('target_topic')
                kafka_config = config.get('kafka_config', {})
                limit = config.get('limit')
                
                if not source_queue or not target_topic:
                    raise Exception(f"Source queue or target topic not specified for MQ-to-Kafka replay component {component.name}")
                
                # Create Kafka connector
                kafka_connector = ConnectorFactory.create_kafka_connector(kafka_config)
                if not kafka_connector:
                    raise Exception(f"Failed to create Kafka connector for MQ-to-Kafka replay component {component.name}")
                
                # Connect to Kafka
                kafka_connected = kafka_connector.connect()
                if not kafka_connected:
                    raise Exception(f"Failed to connect to Kafka for MQ-to-Kafka replay component {component.name}")
                
                count = mq_connector.replay_queue_to_kafka(
                    source_queue=source_queue,
                    target_topic=target_topic,
                    kafka_connector=kafka_connector,
                    limit=limit
                )
                
                # Disconnect from Kafka
                kafka_connector.disconnect()
                
                self._log(f"Replayed {count} messages from MQ queue {source_queue} to Kafka topic {target_topic}")
            
            else:
                raise Exception(f"Unsupported MQ operation type: {operation_type}")
            
            # Disconnect from MQ
            mq_connector.disconnect()
            
        except Exception as e:
            self._log(f"Error executing MQ component {component.name}: {str(e)}")
            raise

    def _simulate_db_component(self, component):
        """Execute a database component using the DBConnector."""
        try:
            from .connectors.connector_factory import ConnectorFactory
            
            # Get component configuration
            config = component.config
            
            # Create DB connector
            db_connector = ConnectorFactory.create_db_connector(config)
            if not db_connector:
                raise Exception(f"Failed to create DB connector for component {component.name}")
            
            # Connect to database
            connected = db_connector.connect()
            if not connected:
                raise Exception(f"Failed to connect to database for component {component.name}")
            
            # Get operation type from component configuration
            operation_type = config.get('operation_type', 'query')
            
            if operation_type == 'query':
                # Execute a query and process results
                query = config.get('query')
                params = config.get('params', {})
                
                if not query:
                    raise Exception(f"No query specified for DB query component {component.name}")
                
                results = db_connector.execute_query(query, params)
                self._log(f"Executed query, returned {len(results)} rows")
                
                # Store results in component output for later use
                component.output = results
            
            elif operation_type == 'update':
                # Execute an update query
                query = config.get('query')
                params = config.get('params', {})
                
                if not query:
                    raise Exception(f"No query specified for DB update component {component.name}")
                
                rows_affected = db_connector.execute_update(query, params)
                self._log(f"Executed update, affected {rows_affected} rows")
            
            elif operation_type == 'batch':
                # Execute a batch of updates
                query = config.get('query')
                params_list = config.get('params_list', [])
                
                if not query:
                    raise Exception(f"No query specified for DB batch component {component.name}")
                
                rows_affected = db_connector.execute_batch(query, params_list)
                self._log(f"Executed batch update, affected {rows_affected} rows")
            
            elif operation_type == 'script':
                # Execute a SQL script
                script = config.get('script')
                
                if not script:
                    raise Exception(f"No script specified for DB script component {component.name}")
                
                success = db_connector.execute_script(script)
                if not success:
                    raise Exception(f"Failed to execute SQL script")
                
                self._log(f"Executed SQL script successfully")
            
            elif operation_type == 'transaction':
                # Execute a series of queries within a transaction
                queries = config.get('queries', [])
                
                if not queries:
                    raise Exception(f"No queries specified for DB transaction component {component.name}")
                
                # Begin transaction
                db_connector.begin_transaction()
                
                try:
                    for query_config in queries:
                        query = query_config.get('query')
                        params = query_config.get('params', {})
                        
                        if query_config.get('type') == 'update':
                            rows_affected = db_connector.execute_update(query, params)
                            self._log(f"Executed update in transaction, affected {rows_affected} rows")
                        else:
                            results = db_connector.execute_query(query, params)
                            self._log(f"Executed query in transaction, returned {len(results)} rows")
                    
                    # Commit transaction
                    db_connector.commit_transaction()
                    self._log(f"Transaction committed successfully")
                except Exception as e:
                    # Rollback transaction on error
                    db_connector.rollback_transaction()
                    self._log(f"Transaction rolled back due to error: {str(e)}")
                    raise
            
            elif operation_type == 'export_to_kafka':
                # Export query results to Kafka
                query = config.get('query')
                params = config.get('params', {})
                topic = config.get('topic')
                kafka_config = config.get('kafka_config', {})
                batch_size = config.get('batch_size', 1000)
                
                if not query or not topic:
                    raise Exception(f"Query or topic not specified for DB-to-Kafka export component {component.name}")
                
                # Create Kafka connector
                kafka_connector = ConnectorFactory.create_kafka_connector(kafka_config)
                if not kafka_connector:
                    raise Exception(f"Failed to create Kafka connector for DB-to-Kafka export component {component.name}")
                
                # Connect to Kafka
                kafka_connected = kafka_connector.connect()
                if not kafka_connected:
                    raise Exception(f"Failed to connect to Kafka for DB-to-Kafka export component {component.name}")
                
                count = db_connector.export_query_to_kafka(
                    query=query,
                    params=params,
                    kafka_connector=kafka_connector,
                    topic=topic,
                    batch_size=batch_size
                )
                
                # Disconnect from Kafka
                kafka_connector.disconnect()
                
                self._log(f"Exported {count} rows to Kafka topic {topic}")
            
            elif operation_type == 'export_to_mq':
                # Export query results to MQ
                query = config.get('query')
                params = config.get('params', {})
                queue_name = config.get('queue_name')
                mq_config = config.get('mq_config', {})
                batch_size = config.get('batch_size', 1000)
                
                if not query or not queue_name:
                    raise Exception(f"Query or queue not specified for DB-to-MQ export component {component.name}")
                
                # Create MQ connector
                mq_connector = ConnectorFactory.create_mq_connector(mq_config)
                if not mq_connector:
                    raise Exception(f"Failed to create MQ connector for DB-to-MQ export component {component.name}")
                
                # Connect to MQ
                mq_connected = mq_connector.connect()
                if not mq_connected:
                    raise Exception(f"Failed to connect to MQ for DB-to-MQ export component {component.name}")
                
                count = db_connector.export_query_to_mq(
                    query=query,
                    params=params,
                    mq_connector=mq_connector,
                    queue_name=queue_name,
                    batch_size=batch_size
                )
                
                # Disconnect from MQ
                mq_connector.disconnect()
                
                self._log(f"Exported {count} rows to MQ queue {queue_name}")
            
            else:
                raise Exception(f"Unsupported DB operation type: {operation_type}")
            
            # Disconnect from database
            db_connector.disconnect()
            
        except Exception as e:
            self._log(f"Error executing DB component {component.name}: {str(e)}")
            raise

    def _simulate_service_component(self, component):
        """Execute a service component."""
        try:
            # Get component configuration
            config = component.config
            
            # Get service type
            service_type = config.get('service_type', 'http')
            
            if service_type == 'http':
                # Execute HTTP request
                import requests
                
                url = config.get('url')
                method = config.get('method', 'GET').upper()
                headers = config.get('headers', {})
                data = config.get('data')
                json_data = config.get('json')
                timeout = config.get('timeout', 30)
                
                if not url:
                    raise Exception(f"No URL specified for HTTP service component {component.name}")
                
                self._log(f"Making {method} request to {url}")
                
                # Make request
                if method == 'GET':
                    response = requests.get(url, headers=headers, params=data, timeout=timeout)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, data=data, json=json_data, timeout=timeout)
                elif method == 'PUT':
                    response = requests.put(url, headers=headers, data=data, json=json_data, timeout=timeout)
                elif method == 'DELETE':
                    response = requests.delete(url, headers=headers, timeout=timeout)
                elif method == 'PATCH':
                    response = requests.patch(url, headers=headers, data=data, json=json_data, timeout=timeout)
                else:
                    raise Exception(f"Unsupported HTTP method: {method}")
                
                # Check response
                response.raise_for_status()
                
                # Store response in component output for later use
                component.output = {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content': response.text,
                }
                
                try:
                    # Try to parse JSON response
                    component.output['json'] = response.json()
                except:
                    pass
                
                self._log(f"HTTP request completed with status code {response.status_code}")
            
            elif service_type == 'grpc':
                self._log(f"GRPC service execution not implemented yet")
                # TODO: Implement gRPC service execution
            
            elif service_type == 'soap':
                self._log(f"SOAP service execution not implemented yet")
                # TODO: Implement SOAP service execution
            
            else:
                raise Exception(f"Unsupported service type: {service_type}")
            
        except Exception as e:
            self._log(f"Error executing service component {component.name}: {str(e)}")
            raise

    def _simulate_api_component(self, component):
        """Execute an API component."""
        try:
            # Get component configuration
            config = component.config
            
            # Get API type
            api_type = config.get('api_type', 'rest')
            
            if api_type == 'rest':
                # Execute REST API request
                import requests
                
                base_url = config.get('base_url')
                endpoint = config.get('endpoint', '')
                method = config.get('method', 'GET').upper()
                headers = config.get('headers', {})
                params = config.get('params', {})
                data = config.get('data')
                json_data = config.get('json')
                auth_type = config.get('auth_type')
                auth_config = config.get('auth_config', {})
                timeout = config.get('timeout', 30)
                
                if not base_url:
                    raise Exception(f"No base URL specified for REST API component {component.name}")
                
                # Construct full URL
                url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else base_url
                
                self._log(f"Making {method} request to {url}")
                
                # Configure authentication
                auth = None
                if auth_type == 'basic':
                    auth = (auth_config.get('username', ''), auth_config.get('password', ''))
                elif auth_type == 'bearer':
                    headers['Authorization'] = f"Bearer {auth_config.get('token', '')}"
                
                # Make request
                if method == 'GET':
                    response = requests.get(url, headers=headers, params=params, auth=auth, timeout=timeout)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, params=params, data=data, json=json_data, auth=auth, timeout=timeout)
                elif method == 'PUT':
                    response = requests.put(url, headers=headers, params=params, data=data, json=json_data, auth=auth, timeout=timeout)
                elif method == 'DELETE':
                    response = requests.delete(url, headers=headers, params=params, auth=auth, timeout=timeout)
                elif method == 'PATCH':
                    response = requests.patch(url, headers=headers, params=params, data=data, json=json_data, auth=auth, timeout=timeout)
                else:
                    raise Exception(f"Unsupported HTTP method: {method}")
                
                # Check response
                response.raise_for_status()
                
                # Store response in component output for later use
                component.output = {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content': response.text,
                }
                
                try:
                    # Try to parse JSON response
                    component.output['json'] = response.json()
                except:
                    pass
                
                self._log(f"API request completed with status code {response.status_code}")
            
            elif api_type == 'graphql':
                # Execute GraphQL API request
                import requests
                
                url = config.get('url')
                query = config.get('query')
                variables = config.get('variables', {})
                headers = config.get('headers', {})
                auth_type = config.get('auth_type')
                auth_config = config.get('auth_config', {})
                timeout = config.get('timeout', 30)
                
                if not url or not query:
                    raise Exception(f"No URL or query specified for GraphQL API component {component.name}")
                
                self._log(f"Making GraphQL request to {url}")
                
                # Configure authentication
                if auth_type == 'basic':
                    auth = (auth_config.get('username', ''), auth_config.get('password', ''))
                elif auth_type == 'bearer':
                    headers['Authorization'] = f"Bearer {auth_config.get('token', '')}"
                else:
                    auth = None
                
                # Make request
                response = requests.post(
                    url,
                    json={'query': query, 'variables': variables},
                    headers=headers,
                    auth=auth,
                    timeout=timeout
                )
                
                # Check response
                response.raise_for_status()
                
                # Store response in component output for later use
                component.output = {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content': response.text,
                }
                
                try:
                    # Try to parse JSON response
                    component.output['json'] = response.json()
                except:
                    pass
                
                self._log(f"GraphQL request completed with status code {response.status_code}")
            
            else:
                raise Exception(f"Unsupported API type: {api_type}")
            
        except Exception as e:
            self._log(f"Error executing API component {component.name}: {str(e)}")
            raise