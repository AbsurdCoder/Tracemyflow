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
    ComponentExecutionStatus
)
from .forms import (
    WorkflowDefinitionForm, 
    WorkflowComponentForm, 
    WorkflowConnectionForm,
    RetryStrategyForm,
    WorkflowExecutionForm
)
from .services.yaml_generator import WorkflowYAMLGenerator
from .services.workflow_executor import WorkflowExecutor

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

@login_required
def execute_workflow(request, workflow_id):
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
    
    recent_executions = WorkflowExecution.objects.filter(
        workflow=workflow
    ).order_by('-started_at')[:5]
    
    context = {
        'workflow': workflow,
        'form': form,
        'recent_executions': recent_executions,
    }
    
    return render(request, 'workflow/execute.html', context)

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