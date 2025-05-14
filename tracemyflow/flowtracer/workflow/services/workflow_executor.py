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