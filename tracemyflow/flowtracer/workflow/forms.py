# workflow/forms.py

from django import forms
from .models import WorkflowDefinition, WorkflowComponent, WorkflowConnection, RetryStrategy
import logging

logger = logging.getLogger(__name__)
class WorkflowDefinitionForm(forms.ModelForm):
    class Meta:
        model = WorkflowDefinition
        fields = ['name', 'description', 'validation_mode', 'is_active']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class WorkflowComponentForm(forms.ModelForm):
    class Meta:
        model = WorkflowComponent
        fields = ['name', 'component_type', 'order', 'config']
        widgets = {
            'config': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'config':
                self.fields[field].widget.attrs.update({'class': 'form-control'})

class WorkflowConnectionForm(forms.ModelForm):
    class Meta:
        model = WorkflowConnection
        fields = ['source', 'target', 'connection_type', 'config']
        widgets = {
            'config': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        }
        
    def __init__(self, workflow, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source'].queryset = WorkflowComponent.objects.filter(workflow=workflow)
        self.fields['target'].queryset = WorkflowComponent.objects.filter(workflow=workflow)
        
        for field in self.fields:
            if field != 'config':
                self.fields[field].widget.attrs.update({'class': 'form-control'})

class RetryStrategyForm(forms.ModelForm):
    class Meta:
        model = RetryStrategy
        fields = ['strategy_type', 'max_retries', 'initial_delay_seconds', 
                  'backoff_factor', 'custom_strategy']
        widgets = {
            'custom_strategy': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'custom_strategy':
                self.fields[field].widget.attrs.update({'class': 'form-control'})
                
        # Show/hide fields based on strategy type
        self.fields['backoff_factor'].widget.attrs.update({
            'data-strategy-type': 'exponential'
        })
        self.fields['custom_strategy'].widget.attrs.update({
            'data-strategy-type': 'custom'
        })

class WorkflowExecutionForm(forms.Form):
    validation_enabled = forms.BooleanField(
        initial=True, 
        required=False,
        label="Enable Validation",
        help_text="When enabled, the workflow will be validated during execution"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['validation_enabled'].widget.attrs.update({'class': 'form-check-input'})


class SubWorkflowExecutionForm(forms.Form):
    start_component = forms.ModelChoiceField(
        queryset=WorkflowComponent.objects.none(),
        label="Start Component",
        help_text="Select the component where the sub-workflow execution should start"
    )
    
    end_component = forms.ModelChoiceField(
        queryset=WorkflowComponent.objects.none(),
        label="End Component",
        help_text="Select the component where the sub-workflow execution should end"
    )
    
    include_start = forms.BooleanField(
        initial=True,
        required=False,
        label="Include Start Component",
        help_text="Include the start component in the execution"
    )
    
    include_end = forms.BooleanField(
        initial=True,
        required=False,
        label="Include End Component",
        help_text="Include the end component in the execution"
    )
    
    validation_enabled = forms.BooleanField(
        initial=True,
        required=False,
        label="Enable Validation",
        help_text="When enabled, the sub-workflow will be validated during execution"
    )
    
    def __init__(self, workflow, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_component'].queryset = WorkflowComponent.objects.filter(workflow=workflow).order_by('order')
        self.fields['end_component'].queryset = WorkflowComponent.objects.filter(workflow=workflow).order_by('order')
        
        # Add Bootstrap classes
        for field in self.fields:
            if isinstance(self.fields[field].widget, forms.CheckboxInput):
                self.fields[field].widget.attrs.update({'class': 'form-check-input'})
            else:
                self.fields[field].widget.attrs.update({'class': 'form-control'})