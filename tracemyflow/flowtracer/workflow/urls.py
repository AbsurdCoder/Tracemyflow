# workflow/urls.py

from django.urls import path
from . import views

app_name = 'workflow'

urlpatterns = [
    # Workflow management
    path('', views.workflow_list, name='list'),
    path('create/', views.workflow_create, name='create'),
    path('<uuid:workflow_id>/edit/', views.workflow_edit, name='edit'),
    path('<uuid:workflow_id>/execute/', views.execute_workflow, name='execute'),
    path('<uuid:workflow_id>/download-yaml/', views.download_yaml, name='download_yaml'),
    path('<uuid:workflow_id>/upload-yaml/', views.upload_yaml, name='upload_yaml'),
    
    # Component management
    path('<uuid:workflow_id>/add-component/', views.add_component, name='add_component'),
    path('component/<int:component_id>/edit/', views.edit_component, name='edit_component'),
    path('component/<int:component_id>/delete/', views.delete_component, name='delete_component'),
    
    # Connection management
    path('<uuid:workflow_id>/add-connection/', views.add_connection, name='add_connection'),
    path('connection/<int:connection_id>/delete/', views.delete_connection, name='delete_connection'),
    
    # Retry strategy management
    path('component/<int:component_id>/add-retry-strategy/', views.add_retry_strategy, name='add_retry_strategy'),
    path('retry-strategy/<int:strategy_id>/update/', views.update_retry_strategy, name='update_retry_strategy'),
    path('retry-strategy/<int:strategy_id>/delete/', views.delete_retry_strategy, name='delete_retry_strategy'),
    
    # Execution management
    path('execution/<uuid:execution_id>/', views.execution_detail, name='execution_detail'),
    path('execution/<uuid:execution_id>/component/<int:component_id>/execute/', 
         views.execute_component, name='execute_component'),
]