# workflow/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
import json
import yaml

from .models import (
    WorkflowDefinition, 
    WorkflowComponent, 
    WorkflowConnection, 
    RetryStrategy,
    WorkflowExecution,
    ComponentExecutionStatus,
    SubWorkflowExecution
)
from .forms import (
    WorkflowDefinitionForm, 
    WorkflowComponentForm, 
    WorkflowConnectionForm,
    RetryStrategyForm,
    WorkflowExecutionForm,
    SubWorkflowExecutionForm
)
from .services.yaml_generator import WorkflowYAMLGenerator
from .services.workflow_executor import WorkflowExecutor
from .services.sub_workflow_executor import SubWorkflowExecutor

import logging

logger = logging.getLogger(__name__)

@login_required
def workflow_list(request):
    workflows = WorkflowDefinition.objects.filter(created_by=request.user).order_by('-updated_at')
    
    # Ensure all workflows have valid IDs
    for workflow in workflows:
        if not workflow.id:
            # Log this unusual situation
            logger.error(f"Workflow without ID found for user {request.user.username}")
    
    paginator = Paginator(workflows, 10)  # Show 10 workflows per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'workflow/list.html', {'page_obj': page_obj})

@login_required
def workflow_create(request):
    if request.method == 'POST':
        form = WorkflowDefinitionForm(request.POST)
        if form.is_valid():
            workflow = form.save(commit=False)
            workflow.created_by = request.user
            workflow.save()
            
            messages.success(request, f"Workflow '{workflow.name}' created successfully.")
            return redirect('workflow:edit', workflow_id=workflow.id)
    else:
        form = WorkflowDefinitionForm()
    
    return render(request, 'workflow/create.html', {'form': form})

@login_required
def workflow_edit(request, workflow_id):
    workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id, created_by=request.user)
    components = WorkflowComponent.objects.filter(workflow=workflow).order_by('order')
    connections = WorkflowConnection.objects.filter(workflow=workflow)
    
    component_form = WorkflowComponentForm()
    connection_form = WorkflowConnectionForm(workflow=workflow)
    
    # Process forms for updating workflow details
    if request.method == 'POST' and 'update_workflow' in request.POST:
        form = WorkflowDefinitionForm(request.POST, instance=workflow)
        if form.is_valid():
            form.save()
            messages.success(request, f"Workflow '{workflow.name}' updated successfully.")
            return redirect('workflow:edit', workflow_id=workflow.id)
    else:
        form = WorkflowDefinitionForm(instance=workflow)
    
    context = {
        'workflow': workflow,
        'form': form,
        'components': components,
        'connections': connections,
        'component_form': component_form,
        'connection_form': connection_form,
    }
    
    return render(request, 'workflow/edit.html', context)

@login_required
def add_component(request, workflow_id):
    workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id, created_by=request.user)
    
    if request.method == 'POST':
        form = WorkflowComponentForm(request.POST)
        if form.is_valid():
            component = form.save(commit=False)
            component.workflow = workflow
            
            # Set order to next available if not specified
            if not component.order:
                max_order = WorkflowComponent.objects.filter(workflow=workflow).order_by('-order').first()
                component.order = (max_order.order + 1) if max_order else 1
            
            # Process config as JSON
            if isinstance(component.config, str) and component.config.strip():
                try:
                    component.config = json.loads(component.config)
                except json.JSONDecodeError:
                    messages.error(request, "Invalid JSON in component configuration.")
                    return redirect('workflow:edit', workflow_id=workflow.id)
            
            component.save()
            messages.success(request, f"Component '{component.name}' added successfully.")
            
            # Update YAML file
            generator = WorkflowYAMLGenerator(workflow.id)
            generator.save_yaml_to_file()
            
            return redirect('workflow:edit', workflow_id=workflow.id)
        else:
            messages.error(request, "Error adding component. Please check the form.")
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def edit_component(request, component_id):
    component = get_object_or_404(WorkflowComponent, pk=component_id)
    workflow = component.workflow
    
    # Check if user owns this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to edit this component.")
        return redirect('workflow:list')
    
    if request.method == 'POST':
        form = WorkflowComponentForm(request.POST, instance=component)
        if form.is_valid():
            updated_component = form.save(commit=False)
            
            # Process config as JSON
            if isinstance(updated_component.config, str) and updated_component.config.strip():
                try:
                    updated_component.config = json.loads(updated_component.config)
                except json.JSONDecodeError:
                    messages.error(request, "Invalid JSON in component configuration.")
                    return redirect('workflow:edit', workflow_id=workflow.id)
            
            updated_component.save()
            messages.success(request, f"Component '{updated_component.name}' updated successfully.")
            
            # Update YAML file
            generator = WorkflowYAMLGenerator(workflow.id)
            generator.save_yaml_to_file()
            
            return redirect('workflow:edit', workflow_id=workflow.id)
        else:
            messages.error(request, "Error updating component. Please check the form.")
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def delete_component(request, component_id):
    component = get_object_or_404(WorkflowComponent, pk=component_id)
    workflow = component.workflow
    
    # Check if user owns this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to delete this component.")
        return redirect('workflow:list')
    
    if request.method == 'POST':
        component_name = component.name
        component.delete()
        messages.success(request, f"Component '{component_name}' deleted successfully.")
        
        # Update YAML file
        generator = WorkflowYAMLGenerator(workflow.id)
        generator.save_yaml_to_file()
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def add_connection(request, workflow_id):
    workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id, created_by=request.user)
    
    if request.method == 'POST':
        form = WorkflowConnectionForm(workflow, request.POST)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.workflow = workflow
            
            # Process config as JSON
            if isinstance(connection.config, str) and connection.config.strip():
                try:
                    connection.config = json.loads(connection.config)
                except json.JSONDecodeError:
                    messages.error(request, "Invalid JSON in connection configuration.")
                    return redirect('workflow:edit', workflow_id=workflow.id)
            
            connection.save()
            messages.success(request, "Connection added successfully.")
            
            # Update YAML file
            generator = WorkflowYAMLGenerator(workflow.id)
            generator.save_yaml_to_file()
            
            return redirect('workflow:edit', workflow_id=workflow.id)
        else:
            messages.error(request, "Error adding connection. Please check the form.")
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def delete_connection(request, connection_id):
    connection = get_object_or_404(WorkflowConnection, pk=connection_id)
    workflow = connection.workflow
    
    # Check if user owns this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to delete this connection.")
        return redirect('workflow:list')
    
    if request.method == 'POST':
        connection.delete()
        messages.success(request, "Connection deleted successfully.")
        
        # Update YAML file
        generator = WorkflowYAMLGenerator(workflow.id)
        generator.save_yaml_to_file()
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def add_retry_strategy(request, component_id):
    component = get_object_or_404(WorkflowComponent, pk=component_id)
    workflow = component.workflow
    
    # Check if user owns this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to add a retry strategy.")
        return redirect('workflow:list')
    
    if request.method == 'POST':
        form = RetryStrategyForm(request.POST)
        if form.is_valid():
            strategy = form.save(commit=False)
            strategy.component = component
            strategy.save()
            
            messages.success(request, f"Retry strategy added to {component.name}.")
            
            # Update YAML file
            generator = WorkflowYAMLGenerator(workflow.id)
            generator.save_yaml_to_file()
            
            return redirect('workflow:edit', workflow_id=workflow.id)
        else:
            messages.error(request, "Error adding retry strategy. Please check the form.")
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def update_retry_strategy(request, strategy_id):
    strategy = get_object_or_404(RetryStrategy, pk=strategy_id)
    component = strategy.component
    workflow = component.workflow
    
    # Check if user owns this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to update this retry strategy.")
        return redirect('workflow:list')
    
    if request.method == 'POST':
        form = RetryStrategyForm(request.POST, instance=strategy)
        if form.is_valid():
            form.save()
            messages.success(request, "Retry strategy updated successfully.")
            
            # Update YAML file
            generator = WorkflowYAMLGenerator(workflow.id)
            generator.save_yaml_to_file()
            
            return redirect('workflow:edit', workflow_id=workflow.id)
        else:
            messages.error(request, "Error updating retry strategy. Please check the form.")
    
    return redirect('workflow:edit', workflow_id=workflow.id)

@login_required
def delete_retry_strategy(request, strategy_id):
    strategy = get_object_or_404(RetryStrategy, pk=strategy_id)
    component = strategy.component
    workflow = component.workflow
    
    # Check if user owns this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to delete this retry strategy.")
        return redirect('workflow:list')
    
    if request.method == 'POST':
        strategy.delete()
        messages.success(request, "Retry strategy deleted successfully.")
        
        # Update YAML file
        generator = WorkflowYAMLGenerator(workflow.id)
        generator.save_yaml_to_file()
    
    return redirect('workflow:edit', workflow_id=workflow.id)
# Update the execute_workflow view function to include recent sub-workflow executions

@login_required
def execute_workflow(request, workflow_id):
    try:
        workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id)
        
        # Check if user has permission to execute this workflow
        if workflow.created_by != request.user:
            messages.error(request, "You don't have permission to execute this workflow.")
            return redirect('workflow:list')
        
        if request.method == 'POST':
            form = WorkflowExecutionForm(request.POST)
            if form.is_valid():
                validation_enabled = form.cleaned_data.get('validation_enabled', True)
                
                # Create execution record
                execution = WorkflowExecution.objects.create(
                    workflow=workflow,
                    started_by=request.user,
                    validation_enabled=validation_enabled
                )
                
                # Execute workflow in background (for a real application, use Celery or similar)
                # For this example, we'll execute it synchronously
                executor = WorkflowExecutor(execution.id)
                status = executor.execute()
                
                messages.success(request, f"Workflow execution completed with status: {status}")
                return redirect('workflow:execution_detail', execution_id=execution.id)
            else:
                messages.error(request, "Error starting workflow execution.")
        else:
            form = WorkflowExecutionForm()
        
        # Get components
        components = WorkflowComponent.objects.filter(workflow=workflow).order_by('order')
        
        # Get connections
        connections = WorkflowConnection.objects.filter(workflow=workflow)
        
        # Get recent full workflow executions
        recent_executions = WorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-started_at')[:5]
        
        # Get recent sub-workflow executions
        recent_sub_executions = SubWorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-started_at')[:5]
        
        context = {
            'workflow': workflow,
            'form': form,
            'components': components,
            'connections': connections,
            'recent_executions': recent_executions,
            'recent_sub_executions': recent_sub_executions,
        }
        
        return render(request, 'workflow/execute.html', context)
    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('workflow:list')
    
@login_required
def execution_detail(request, execution_id):
    execution = get_object_or_404(WorkflowExecution, pk=execution_id)
    workflow = execution.workflow
    
    # Check if user has permission to view this execution
    if execution.started_by != request.user and workflow.created_by != request.user:
        messages.error(request, "You don't have permission to view this execution.")
        return redirect('workflow:list')
    
    component_statuses = ComponentExecutionStatus.objects.filter(
        workflow_execution=execution
    ).order_by('component__order')
    
    context = {
        'execution': execution,
        'workflow': workflow,
        'component_statuses': component_statuses,
    }
    
    return render(request, 'workflow/execution_detail.html', context)

@login_required
def execute_component(request, execution_id, component_id):
    execution = get_object_or_404(WorkflowExecution, pk=execution_id)
    workflow = execution.workflow
    
    # Check if user has permission
    if execution.started_by != request.user and workflow.created_by != request.user:
        messages.error(request, "You don't have permission to execute this component.")
        return redirect('workflow:list')
    
    # Only allow executing components if workflow is partially completed or failed
    if execution.status not in ['partially_completed', 'failed']:
        messages.error(request, "Cannot execute individual components for workflows that are not partially completed or failed.")
        return redirect('workflow:execution_detail', execution_id=execution.id)
    
    # Execute just this component
    executor = WorkflowExecutor(execution.id)
    status = executor.execute_sub_workflow(component_id)
    
    messages.success(request, f"Component execution completed with status: {status}")
    return redirect('workflow:execution_detail', execution_id=execution.id)

@login_required
def download_yaml(request, workflow_id):
    workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id)
    
    # Check if user has permission to download this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to download this workflow.")
        return redirect('workflow:list')
    
    # Generate or update YAML
    generator = WorkflowYAMLGenerator(workflow.id)
    yaml_data = generator.generate_yaml()
    
    # Convert to YAML string
    yaml_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
    
    # Create response
    response = HttpResponse(yaml_content, content_type='application/x-yaml')
    response['Content-Disposition'] = f'attachment; filename="{workflow.name.replace(" ", "_").lower()}.yaml"'
    
    return response

@login_required
def upload_yaml(request, workflow_id):
    workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id)
    
    # Check if user has permission to modify this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to upload to this workflow.")
        return redirect('workflow:list')
    
    if request.method == 'POST' and request.FILES.get('yaml_file'):
        yaml_file = request.FILES['yaml_file']
        
        try:
            # Parse YAML content
            yaml_content = yaml_file.read().decode('utf-8')
            yaml_data = yaml.safe_load(yaml_content)
            
            # TODO: Implement logic to update workflow components and connections from the uploaded YAML
            # This is complex and would require validation and mapping between YAML and database models
            
            messages.success(request, "YAML file uploaded successfully.")
        except Exception as e:
            messages.error(request, f"Error processing YAML file: {str(e)}")
        
        return redirect('workflow:edit', workflow_id=workflow.id)
    
    return redirect('workflow:edit', workflow_id=workflow.id)



@login_required
def execute_sub_workflow(request, workflow_id):
    workflow = get_object_or_404(WorkflowDefinition, pk=workflow_id)
    
    # Check if user has permission to execute this workflow
    if workflow.created_by != request.user:
        messages.error(request, "You don't have permission to execute this workflow.")
        return redirect('workflow:list')
    
    # Check if workflow has components
    components = WorkflowComponent.objects.filter(workflow=workflow).order_by('order')
    if components.count() < 2:
        messages.error(request, "Workflow must have at least 2 components to execute a sub-workflow.")
        return redirect('workflow:execute', workflow_id=workflow.id)
    
    if request.method == 'POST':
        form = SubWorkflowExecutionForm(workflow, request.POST)
        if form.is_valid():
            start_component = form.cleaned_data['start_component']
            end_component = form.cleaned_data['end_component']
            include_start = form.cleaned_data['include_start']
            include_end = form.cleaned_data['include_end']
            validation_enabled = form.cleaned_data['validation_enabled']
            
            # Create sub-workflow execution record
            sub_execution = SubWorkflowExecution.objects.create(
                workflow=workflow,
                started_by=request.user,
                validation_enabled=validation_enabled,
                start_component=start_component,
                end_component=end_component,
                include_start=include_start,
                include_end=include_end
            )
            
            # Execute sub-workflow
            executor = SubWorkflowExecutor(sub_execution.id)
            status = executor.execute()
            
            messages.success(request, f"Sub-workflow execution completed with status: {status}")
            return redirect('workflow:sub_execution_detail', sub_execution_id=sub_execution.id)
        else:
            messages.error(request, "Error starting sub-workflow execution.")
    else:
        form = SubWorkflowExecutionForm(workflow)
    
    recent_executions = SubWorkflowExecution.objects.filter(
        workflow=workflow
    ).order_by('-started_at')[:5]
    
    context = {
        'workflow': workflow,
        'components': components,
        'form': form,
        'recent_executions': recent_executions,
    }
    
    return render(request, 'workflow/execute_sub_workflow.html', context)

@login_required
def sub_execution_detail(request, sub_execution_id):
    sub_execution = get_object_or_404(SubWorkflowExecution, pk=sub_execution_id)
    workflow = sub_execution.workflow
    
    # Check if user has permission to view this execution
    if sub_execution.started_by != request.user and workflow.created_by != request.user:
        messages.error(request, "You don't have permission to view this execution.")
        return redirect('workflow:list')
    
    # Get components included in this sub-workflow
    components = []
    start_order = sub_execution.start_component.order
    end_order = sub_execution.end_component.order
    
    # Ensure start_order is less than end_order
    if start_order > end_order:
        start_order, end_order = end_order, start_order
    
    # Adjust range based on include_start and include_end
    if sub_execution.include_start and sub_execution.include_end:
        components = WorkflowComponent.objects.filter(
            workflow=workflow, 
            order__gte=start_order, 
            order__lte=end_order
        ).order_by('order')
    elif sub_execution.include_start and not sub_execution.include_end:
        components = WorkflowComponent.objects.filter(
            workflow=workflow, 
            order__gte=start_order, 
            order__lt=end_order
        ).order_by('order')
    elif not sub_execution.include_start and sub_execution.include_end:
        components = WorkflowComponent.objects.filter(
            workflow=workflow, 
            order__gt=start_order, 
            order__lte=end_order
        ).order_by('order')
    else:  # not include_start and not include_end
        components = WorkflowComponent.objects.filter(
            workflow=workflow, 
            order__gt=start_order, 
            order__lt=end_order
        ).order_by('order')
    
    # Get component statuses
    if sub_execution.parent_execution:
        component_statuses = ComponentExecutionStatus.objects.filter(
            workflow_execution=sub_execution.parent_execution,
            component__in=components
        ).order_by('component__order')
    else:
        component_statuses = ComponentExecutionStatus.objects.filter(
            component__in=components
        ).order_by('component__order')
    
    context = {
        'sub_execution': sub_execution,
        'workflow': workflow,
        'component_statuses': component_statuses,
        'components': components,
    }
    
    return render(request, 'workflow/sub_execution_detail.html', context)

@login_required
def execute_component_in_sub_workflow(request, sub_execution_id, component_id):
    sub_execution = get_object_or_404(SubWorkflowExecution, pk=sub_execution_id)
    workflow = sub_execution.workflow
    
    # Check if user has permission
    if sub_execution.started_by != request.user and workflow.created_by != request.user:
        messages.error(request, "You don't have permission to execute this component.")
        return redirect('workflow:list')
    
    # Only allow executing components if sub-workflow is partially completed or failed
    if sub_execution.status not in ['partially_completed', 'failed']:
        messages.error(request, "Cannot execute individual components for sub-workflows that are not partially completed or failed.")
        return redirect('workflow:sub_execution_detail', sub_execution_id=sub_execution.id)
    
    # Check if component is part of this sub-workflow
    component = get_object_or_404(WorkflowComponent, pk=component_id)
    start_order = sub_execution.start_component.order
    end_order = sub_execution.end_component.order
    
    # Ensure start_order is less than end_order
    if start_order > end_order:
        start_order, end_order = end_order, start_order
    
    # Check if component is in the sub-workflow range
    if (component.order < start_order) or (component.order > end_order):
        messages.error(request, "Component is not part of this sub-workflow.")
        return redirect('workflow:sub_execution_detail', sub_execution_id=sub_execution.id)
    
    # Execute just this component
    executor = SubWorkflowExecutor(sub_execution.id)
    
    # Create a single component list
    single_component = [component]
    
    # Execute component
    try:
        # Get or create component status
        if sub_execution.parent_execution:
            component_status, created = ComponentExecutionStatus.objects.get_or_create(
                workflow_execution=sub_execution.parent_execution,
                component=component,
                defaults={'status': 'pending'}
            )
        else:
            component_status, created = ComponentExecutionStatus.objects.get_or_create(
                component=component,
                defaults={'status': 'pending'}
            )
        
        # Reset component status
        component_status.status = 'pending'
        component_status.started_at = None
        component_status.completed_at = None
        component_status.retry_count = 0
        component_status.error_message = ''
        component_status.save()
        
        # Execute component
        executor._execute_component(component, component_status)
        status = component_status.status
        
        messages.success(request, f"Component execution completed with status: {status}")
    except Exception as e:
        messages.error(request, f"Error executing component: {str(e)}")
    
    return redirect('workflow:sub_execution_detail', sub_execution_id=sub_execution.id)