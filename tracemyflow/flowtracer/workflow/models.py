# workflow/models.py

from django.db import models
from django.contrib.auth.models import User
import uuid
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class WorkflowDefinition(models.Model):
    VALIDATION_CHOICES = [
        ('required', 'Required'),
        ('optional', 'Optional'),
        ('none', 'None'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflows')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validation_mode = models.CharField(max_length=10, choices=VALIDATION_CHOICES, default='optional')
    is_active = models.BooleanField(default=True)
    yaml_file_path = models.CharField(max_length=500, blank=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.yaml_file_path:
            filename = f"workflow_{self.id}.yaml"
            self.yaml_file_path = os.path.join(settings.WORKFLOW_YAML_DIR, filename)
            self.save(update_fields=['yaml_file_path'])

class WorkflowComponent(models.Model):
    COMPONENT_TYPES = [
        ('kafka', 'Kafka'),
        ('mq', 'Message Queue'),
        ('db', 'Database'),
        ('service', 'Service'),
        ('api', 'API'),
    ]
    
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='components')
    name = models.CharField(max_length=255)
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPES)
    order = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.name} ({self.get_component_type_display()})"

class WorkflowConnection(models.Model):
    CONNECTION_TYPES = [
        ('kafka_to_kafka', 'Kafka to Kafka Replay'),
        ('kafka_to_mq', 'Kafka to MQ Replay'),
        ('mq_to_mq', 'MQ to MQ Replay'),
        ('mq_to_kafka', 'MQ to Kafka Replay'),
        ('db_operation', 'DB Updates and Queries'),
    ]
    
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='connections')
    source = models.ForeignKey(WorkflowComponent, on_delete=models.CASCADE, related_name='outgoing_connections')
    target = models.ForeignKey(WorkflowComponent, on_delete=models.CASCADE, related_name='incoming_connections')
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)
    config = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.source.name} to {self.target.name} ({self.get_connection_type_display()})"

class RetryStrategy(models.Model):
    STRATEGY_TYPES = [
        ('fixed', 'Fixed Interval'),
        ('exponential', 'Exponential Backoff'),
        ('custom', 'Custom Strategy'),
    ]
    
    component = models.ForeignKey(WorkflowComponent, on_delete=models.CASCADE, related_name='retry_strategies')
    strategy_type = models.CharField(max_length=20, choices=STRATEGY_TYPES)
    max_retries = models.PositiveIntegerField(default=3)
    initial_delay_seconds = models.PositiveIntegerField(default=5)
    backoff_factor = models.FloatField(default=2.0, help_text="For exponential backoff strategy")
    custom_strategy = models.TextField(blank=True, help_text="Custom retry logic in YAML format")
    
    def __str__(self):
        return f"{self.component.name} - {self.get_strategy_type_display()}"

class WorkflowExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partially_completed', 'Partially Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='executions')
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflow_executions')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    validation_enabled = models.BooleanField(default=True)
    execution_log = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.workflow.name} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

class ComponentExecutionStatus(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name='component_statuses')
    component = models.ForeignKey(WorkflowComponent, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.component.name} - {self.get_status_display()}"
    
class SubWorkflowExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partially_completed', 'Partially Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='sub_executions')
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sub_workflow_executions')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    validation_enabled = models.BooleanField(default=True)
    execution_log = models.TextField(blank=True)
    
    # Start and end components define the sub-workflow boundaries
    start_component = models.ForeignKey(WorkflowComponent, on_delete=models.CASCADE, related_name='sub_workflow_starts')
    end_component = models.ForeignKey(WorkflowComponent, on_delete=models.CASCADE, related_name='sub_workflow_ends')
    
    # Whether to include the start and end components in execution
    include_start = models.BooleanField(default=True)
    include_end = models.BooleanField(default=True)
    
    # Track parent execution if this is part of a larger execution
    parent_execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, 
                                        related_name='child_executions', null=True, blank=True)
    
    def __str__(self):
        return f"SubWorkflow: {self.workflow.name} ({self.start_component.name} to {self.end_component.name})"