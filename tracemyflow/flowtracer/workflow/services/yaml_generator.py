# workflow/services/yaml_generator.py

import yaml
import os
from django.conf import settings
from ..models import WorkflowDefinition, WorkflowComponent, WorkflowConnection, RetryStrategy

class WorkflowYAMLGenerator:
    def __init__(self, workflow_id):
        self.workflow = WorkflowDefinition.objects.get(pk=workflow_id)
        self.components = WorkflowComponent.objects.filter(workflow=self.workflow).order_by('order')
        self.connections = WorkflowConnection.objects.filter(workflow=self.workflow)
        
    def generate_yaml(self):
        """Generate YAML representation of workflow"""
        yaml_data = {
            'workflow': {
                'id': str(self.workflow.id),
                'name': self.workflow.name,
                'description': self.workflow.description,
                'created_by': self.workflow.created_by.username,
                'validation_mode': self.workflow.validation_mode,
                'components': self._generate_components_yaml(),
                'connections': self._generate_connections_yaml(),
            }
        }
        
        return yaml_data
    
    def _generate_components_yaml(self):
        """Generate YAML for workflow components"""
        components_data = []
        
        for component in self.components:
            component_data = {
                'id': str(component.id),
                'name': component.name,
                'type': component.component_type,
                'order': component.order,
                'config': component.config,
            }
            
            # Add retry strategies if any
            retry_strategies = RetryStrategy.objects.filter(component=component)
            if retry_strategies.exists():
                component_data['retry_strategies'] = []
                for strategy in retry_strategies:
                    strategy_data = {
                        'type': strategy.strategy_type,
                        'max_retries': strategy.max_retries,
                        'initial_delay_seconds': strategy.initial_delay_seconds,
                    }
                    
                    if strategy.strategy_type == 'exponential':
                        strategy_data['backoff_factor'] = strategy.backoff_factor
                    elif strategy.strategy_type == 'custom':
                        strategy_data['custom_logic'] = strategy.custom_strategy
                    
                    component_data['retry_strategies'].append(strategy_data)
            
            components_data.append(component_data)
        
        return components_data
    
    def _generate_connections_yaml(self):
        """Generate YAML for workflow connections"""
        connections_data = []
        
        for connection in self.connections:
            connection_data = {
                'id': str(connection.id),
                'type': connection.connection_type,
                'source': {
                    'id': str(connection.source.id),
                    'name': connection.source.name,
                },
                'target': {
                    'id': str(connection.target.id),
                    'name': connection.target.name,
                },
                'config': connection.config,
            }
            
            connections_data.append(connection_data)
        
        return connections_data
    
    def save_yaml_to_file(self):
        """Save the workflow definition to a YAML file"""
        yaml_data = self.generate_yaml()
        os.makedirs(settings.WORKFLOW_YAML_DIR, exist_ok=True)
        
        file_path = self.workflow.yaml_file_path
        
        with open(file_path, 'w') as yaml_file:
            yaml.dump(yaml_data, yaml_file, default_flow_style=False, sort_keys=False)
        
        return file_path
    
    def load_yaml_from_file(self):
        """Load workflow definition from YAML file"""
        file_path = self.workflow.yaml_file_path
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r') as yaml_file:
            yaml_data = yaml.safe_load(yaml_file)
        
        return yaml_data