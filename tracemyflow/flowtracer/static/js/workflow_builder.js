/* Workflow Builder JavaScript */

// Main configuration object for the workflow builder
const workflowBuilder = {
    jsPlumbInstance: null,
    containerId: 'workflow-diagram',
    
    // Initialize the workflow builder
    init: function() {
        // Only initialize if the container exists
        if (!document.getElementById(this.containerId)) {
            return;
        }
        
        // Create jsPlumb instance
        this.jsPlumbInstance = jsPlumb.getInstance({
            Connector: ['Bezier', { curviness: 60 }],
            Container: this.containerId
        });
        
        // Set default appearance for connections
        this.jsPlumbInstance.importDefaults({
            Endpoint: ['Dot', { radius: 5 }],
            EndpointStyle: { fill: '#5bc0de' },
            PaintStyle: { stroke: '#5bc0de', strokeWidth: 2 },
            HoverPaintStyle: { stroke: '#337ab7', strokeWidth: 3 },
            ConnectionOverlays: [
                ['Arrow', { width: 10, length: 10, location: 1 }]
            ]
        });
        
        // Bind events
        this.bindEvents();
    },
    
    // Bind all necessary events
    bindEvents: function() {
        // Component type change event in add component modal
        $('#id_component_type').on('change', function() {
            const componentType = $(this).val();
            let configTemplate = {};
            
            // Set default config based on component type
            switch(componentType) {
                case 'kafka':
                    configTemplate = {
                        "topic": "example-topic",
                        "bootstrap_servers": "localhost:9092",
                        "group_id": "example-group",
                        "auto_offset_reset": "earliest"
                    };
                    break;
                case 'mq':
                    configTemplate = {
                        "queue_name": "example-queue",
                        "host": "localhost",
                        "port": 5672,
                        "username": "guest",
                        "password": "guest"
                    };
                    break;
                case 'db':
                    configTemplate = {
                        "database_type": "postgresql",
                        "host": "localhost",
                        "port": 5432,
                        "database": "example_db",
                        "username": "postgres",
                        "password": "password"
                    };
                    break;
                case 'service':
                    configTemplate = {
                        "service_url": "http://example-service:8080/api",
                        "timeout_seconds": 30,
                        "retry_attempts": 3
                    };
                    break;
                case 'api':
                    configTemplate = {
                        "api_url": "https://api.example.com/v1",
                        "method": "GET",
                        "headers": {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer TOKEN"
                        }
                    };
                    break;
                default:
                    configTemplate = {};
            }
            
            // Set the config textarea with the template
            $('#id_config').val(JSON.stringify(configTemplate, null, 2));
        });
        
        // Connection type change event in add connection modal
        $('#id_connection_type').on('change', function() {
            const connectionType = $(this).val();
            let configTemplate = {};
            
            // Set default config based on connection type
            switch(connectionType) {
                case 'kafka_to_kafka':
                    configTemplate = {
                        "source_topic": "source-topic",
                        "target_topic": "target-topic",
                        "message_filter": ".*",
                        "transform_script": ""
                    };
                    break;
                case 'kafka_to_mq':
                    configTemplate = {
                        "source_topic": "source-topic",
                        "target_queue": "target-queue",
                        "message_filter": ".*",
                        "transform_script": ""
                    };
                    break;
                case 'mq_to_mq':
                    configTemplate = {
                        "source_queue": "source-queue",
                        "target_queue": "target-queue",
                        "message_filter": ".*",
                        "transform_script": ""
                    };
                    break;
                case 'mq_to_kafka':
                    configTemplate = {
                        "source_queue": "source-queue",
                        "target_topic": "target-topic",
                        "message_filter": ".*",
                        "transform_script": ""
                    };
                    break;
                case 'db_operation':
                    configTemplate = {
                        "operation_type": "query",
                        "query": "SELECT * FROM example_table WHERE condition = :param",
                        "parameters": {
                            "param": "value"
                        },
                        "timeout_seconds": 30
                    };
                    break;
                default:
                    configTemplate = {};
            }
            
            // Set the config textarea with the template
            $('#id_connection_config').val(JSON.stringify(configTemplate, null, 2));
        });
        
        // Strategy type change event in retry strategy modal
        $('#id_strategy_type').on('change', function() {
            const strategyType = $(this).val();
            
            // Show/hide fields based on strategy type
            $('.strategy-field').hide();
            $(`.strategy-field[data-strategy-type="${strategyType}"]`).show();
            
            // Set default values for custom strategy
            if (strategyType === 'custom') {
                const customTemplate = `# Custom retry strategy YAML
strategy: custom
max_retries: 5
delays:
  - 5  # First retry after 5 seconds
  - 10 # Second retry after 10 seconds
  - 20 # Third retry after 20 seconds
  - 40 # Fourth retry after 40 seconds
  - 60 # Fifth retry after 60 seconds
conditions:
  - type: status_code
    values: [500, 502, 503, 504]
  - type: exception
    values: ["ConnectionError", "Timeout"]`;
                
                $('#id_custom_strategy').val(customTemplate);
            }
        });
    },
    
    // Load components and connections from data
    loadWorkflowData: function(components, connections) {
        const container = document.getElementById(this.containerId);
        
        // Clear previous diagram
        container.innerHTML = '';
        
        if (!components || components.length === 0) {
            container.innerHTML = '<div class="d-flex justify-content-center align-items-center h-100"><div class="text-center p-4"><i class="fas fa-project-diagram fa-4x text-muted mb-3"></i><h5>No Components</h5><p class="text-muted">Add components and connections to visualize your workflow.</p></div></div>';
            return;
        }
        
        // Calculate position based on component order
        const calculatePosition = (order, total) => {
            const rows = Math.ceil(Math.sqrt(total));
            const cols = Math.ceil(total / rows);
            const row = Math.floor((order - 1) / cols);
            const col = (order - 1) % cols;
            return {
                left: 150 + col * 200,
                top: 100 + row * 150
            };
        };
        
        // Create component elements
        components.forEach(component => {
            const position = calculatePosition(component.order, components.length);
            
            // Create component div
            const componentEl = document.createElement('div');
            componentEl.id = `component-${component.id}`;
            componentEl.className = `workflow-component ${component.type}-component`;
            componentEl.style.left = `${position.left}px`;
            componentEl.style.top = `${position.top}px`;
            
            // Create component header
            const headerEl = document.createElement('div');
            headerEl.className = 'component-header';
            headerEl.innerHTML = `
                <span class="component-type">${component.type.toUpperCase()}</span>
                <span class="component-drag-handle"><i class="fas fa-arrows-alt"></i></span>
            `;
            componentEl.appendChild(headerEl);
            
            // Create component body
            const bodyEl = document.createElement('div');
            bodyEl.className = 'component-body';
            bodyEl.innerHTML = `<span class="component-name">${component.name}</span>`;
            componentEl.appendChild(bodyEl);
            
            // Add to container
            container.appendChild(componentEl);
            
            // Make component draggable
            this.jsPlumbInstance.draggable(componentEl, {
                handle: '.component-drag-handle',
                containment: container
            });
            
            // Add connection endpoints
            this.jsPlumbInstance.addEndpoint(componentEl, {
                isSource: true,
                maxConnections: -1,
                anchor: 'Right',
                endpoint: ['Dot', { radius: 5 }],
                paintStyle: { fill: '#5bc0de' },
                connectorStyle: { stroke: '#5bc0de', strokeWidth: 2 },
                connectorHoverStyle: { stroke: '#337ab7', strokeWidth: 3 }
            });
            
            this.jsPlumbInstance.addEndpoint(componentEl, {
                isTarget: true,
                maxConnections: -1,
                anchor: 'Left',
                endpoint: ['Dot', { radius: 5 }],
                paintStyle: { fill: '#f0ad4e' },
                connectorStyle: { stroke: '#5bc0de', strokeWidth: 2 },
                connectorHoverStyle: { stroke: '#337ab7', strokeWidth: 3 }
            });
        });
        
        // Create connections
        this.jsPlumbInstance.batch(() => {
            connections.forEach(connection => {
                this.jsPlumbInstance.connect({
                    source: `component-${connection.source}`,
                    target: `component-${connection.target}`,
                    overlays: [
                        ['Label', { label: connection.type.replace(/_/g, ' ').toUpperCase(), location: 0.5, cssClass: 'connection-label' }]
                    ]
                });
            });
        });
        
        // Render when everything is ready
        this.jsPlumbInstance.repaintEverything();
    }
};

// Initialize when the document is ready
$(document).ready(function() {
    // Initialize the workflow builder if we're on the right page
    if ($('#workflow-diagram').length) {
        workflowBuilder.init();
        
        // Load workflow data when the visual tab is shown
        $('#visual-tab').on('shown.bs.tab', function() {
            const components = [];
            const connections = [];
            
            // Collect component data from the page
            $('.workflow-component').each(function() {
                const id = $(this).attr('id').replace('component-', '');
                const name = $(this).find('.component-name').text();
                const type = $(this).find('.component-type').text().toLowerCase();
                const order = $(this).data('order') || 1;
                
                components.push({
                    id: id,
                    name: name,
                    type: type,
                    order: order
                });
            });
            
            // Initialize the diagram
            workflowBuilder.loadWorkflowData(components, connections);
        });
    }
    
    // Initialize form validation
    $('form').submit(function() {
        // Validate JSON fields
        const jsonFields = $(this).find('textarea[name="config"]');
        let hasError = false;
        
        jsonFields.each(function() {
            const value = $(this).val().trim();
            if (value) {
                try {
                    JSON.parse(value);
                    $(this).removeClass('is-invalid');
                } catch (e) {
                    $(this).addClass('is-invalid');
                    if (!$(this).next('.invalid-feedback').length) {
                        $(this).after('<div class="invalid-feedback">Invalid JSON format</div>');
                    }
                    hasError = true;
                }
            }
        });
        
        return !hasError;
    });
});