# workflow/services/sub_workflow_executor.py

import time
import logging
from datetime import datetime
from django.utils import timezone
from ..models import (
    WorkflowDefinition, 
    WorkflowComponent,
    SubWorkflowExecution,
    ComponentExecutionStatus,
    RetryStrategy
)

logger = logging.getLogger(__name__)

class SubWorkflowExecutor:
    """Executor for sub-workflows that run only specific portions of a workflow"""
    
    def __init__(self, sub_execution_id):
        self.sub_execution = SubWorkflowExecution.objects.get(pk=sub_execution_id)
        self.workflow = self.sub_execution.workflow
        self.validation_enabled = self.sub_execution.validation_enabled
        self.start_component = self.sub_execution.start_component
        self.end_component = self.sub_execution.end_component
        self.include_start = self.sub_execution.include_start
        self.include_end = self.sub_execution.include_end
        
        # Determine components in the path from start to end
        self.components = self._get_components_in_path()
        
    def _get_components_in_path(self):
        """
        Determine which components should be included in the sub-workflow execution,
        based on the path from start to end component.
        """
        # Get all components in the workflow
        all_components = WorkflowComponent.objects.filter(workflow=self.workflow).order_by('order')
        
        # Calculate the range based on order values
        start_order = self.start_component.order
        end_order = self.end_component.order
        
        # Ensure proper order range (handle case where end comes before start in order)
        if start_order > end_order:
            start_order, end_order = end_order, start_order
            # Switch start and end components
            self.start_component, self.end_component = self.end_component, self.start_component
            # Also switch include flags
            self.include_start, self.include_end = self.include_end, self.include_start
        
        # Filter components within the range
        if self.include_start and self.include_end:
            components = all_components.filter(order__gte=start_order, order__lte=end_order)
        elif self.include_start and not self.include_end:
            components = all_components.filter(order__gte=start_order, order__lt=end_order)
        elif not self.include_start and self.include_end:
            components = all_components.filter(order__gt=start_order, order__lte=end_order)
        else:  # not include_start and not include_end
            components = all_components.filter(order__gt=start_order, order__lt=end_order)
        
        return components
    
    def execute(self):
        """Execute the sub-workflow"""
        self.sub_execution.status = 'running'
        self.sub_execution.save()
        
        log_message = (f"Starting sub-workflow execution: {self.workflow.name} "
                      f"(From: {self.start_component.name} To: {self.end_component.name})")
        self._log(log_message)
        
        try:
            # Create component execution status records
            self._initialize_component_statuses()
            
            # Execute each component in order
            for component in self.components:
                component_status = ComponentExecutionStatus.objects.get(
                    workflow_execution=self.sub_execution.parent_execution if self.sub_execution.parent_execution else None,
                    component=component
                )
                
                self._execute_component(component, component_status)
                
            # Check if all components completed successfully
            all_completed = self._check_all_components_completed()
            
            if all_completed:
                self.sub_execution.status = 'completed'
                log_message = (f"Sub-workflow execution completed successfully: "
                              f"{self.workflow.name} (From: {self.start_component.name} To: {self.end_component.name})")
            else:
                self.sub_execution.status = 'partially_completed'
                log_message = (f"Sub-workflow execution partially completed: "
                              f"{self.workflow.name} (From: {self.start_component.name} To: {self.end_component.name})")
            
            self._log(log_message)
            
        except Exception as e:
            self.sub_execution.status = 'failed'
            error_message = f"Sub-workflow execution failed: {str(e)}"
            self._log(error_message)
            logger.exception(error_message)
        
        self.sub_execution.completed_at = timezone.now()
        self.sub_execution.save()
        
        return self.sub_execution.status
    
    def _initialize_component_statuses(self):
        """Initialize status records for all components in the sub-workflow"""
        # If this sub-workflow has a parent execution, use its component statuses
        if self.sub_execution.parent_execution:
            # Simply mark components as pending again if they're in our sub-workflow
            for component in self.components:
                try:
                    status = ComponentExecutionStatus.objects.get(
                        workflow_execution=self.sub_execution.parent_execution,
                        component=component
                    )
                    status.status = 'pending'
                    status.started_at = None
                    status.completed_at = None
                    status.retry_count = 0
                    status.error_message = ''
                    status.save()
                except ComponentExecutionStatus.DoesNotExist:
                    # Create new status if it doesn't exist in parent
                    ComponentExecutionStatus.objects.create(
                        workflow_execution=self.sub_execution.parent_execution,
                        component=component,
                        status='pending'
                    )
        else:
            # Create new status records for standalone sub-workflow
            for component in self.components:
                ComponentExecutionStatus.objects.create(
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
        """Check if all components in the sub-workflow completed successfully"""
        if self.sub_execution.parent_execution:
            statuses = ComponentExecutionStatus.objects.filter(
                workflow_execution=self.sub_execution.parent_execution,
                component__in=self.components
            )
        else:
            statuses = ComponentExecutionStatus.objects.filter(
                component__in=self.components
            )
        
        return all(status.status == 'completed' for status in statuses)
    
    def _log(self, message):
        """Add a log message to the execution log"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        self.sub_execution.execution_log += log_entry
        self.sub_execution.save(update_fields=['execution_log'])
        
        logger.info(message)
    
    # Simulation methods for different component types
    def _simulate_kafka_component(self, component):
        """Simulate execution of a Kafka component"""
        time.sleep(0.5)  # Simulate processing time
        self._log(f"Simulating Kafka component execution: {component.name}")
    
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
