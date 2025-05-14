# workflow/forms.py

from django import forms
from .models import WorkflowDefinition, WorkflowComponent, WorkflowConnection, RetryStrategy

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