document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
    const messagesContainer = document.getElementById('messages');
    const errorMessage = document.getElementById('error-message');
    const loadingIndicator = document.getElementById('loading-indicator');
const modelOptions = document.querySelectorAll('.model-option');
const apiKeyContainer = document.getElementById('api-key-container');
const apiKeyInput = document.getElementById('api-key');
const submitApiKeyButton = document.getElementById('submit-api-key');
const useDefaultKeyRadio = document.getElementById('use-default-key');
const useCustomKeyRadio = document.getElementById('use-custom-key');
const customKeyInput = document.getElementById('custom-key-input');
    const clearChatButton = document.getElementById('clear-chat');
    const sourcesPanel = document.getElementById('sources-panel');
    const sourcesList = document.getElementById('sources-list');
    const selectAllCheckbox = document.getElementById('select-all-sources');
const apiKeyNotification = document.getElementById('api-key-notification');

// Variables
let selectedModel = null;
let selectedSourceIds = [];
let modelApiKeys = {}; // Store API keys for different models
let currentApiKeySubmitted = false; // Track if current API key has been submitted
let useDefaultApiKey = true; // Default to using default API key
    
    // Auto resize textarea as user types
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        
        // Enable send button if there's text
        sendButton.disabled = !this.value.trim();
    });
    
    // Handle Enter key to send message
    userInput.addEventListener('keydown', function(e) {
        // Send on Enter without shift
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.disabled) {
            sendMessage();
            }
        }
    });
    
    // Send button click
    sendButton.addEventListener('click', sendMessage);
    
    // Model selection
    modelOptions.forEach(option => {
        option.addEventListener('click', function() {
            const newModelId = this.dataset.model;
            const needsKey = this.dataset.needsKey === 'true';
            
            // If switching to a different model
            if (selectedModel && selectedModel.id !== newModelId) {
                // Reset submission state for new model
                currentApiKeySubmitted = false;
            }
            
            // Remove selected class from all options
            modelOptions.forEach(opt => opt.classList.remove('selected'));
            
            // Add selected class to clicked option
            this.classList.add('selected');
            
            // Store selected model
            selectedModel = {
                id: newModelId,
                name: this.querySelector('.model-name').textContent,
                needsKey: needsKey
            };
            
            // Show/hide API key input
            if (selectedModel.needsKey) {
                // Check if default API key is available
                checkDefaultApiKey(selectedModel.id);
                
                apiKeyContainer.classList.remove('hidden');
                
                // Reset to default option
                useDefaultKeyRadio.checked = true;
                useCustomKeyRadio.checked = false;
                customKeyInput.classList.add('hidden');
                useDefaultApiKey = true;
                
                // If we have a saved key for this model and it's for custom entry
                if (modelApiKeys[selectedModel.id] && !currentApiKeySubmitted) {
                    apiKeyInput.value = modelApiKeys[selectedModel.id];
                } else if (!currentApiKeySubmitted) {
                    // Clear the input when switching to a new model that needs a key
                    apiKeyInput.value = '';
                }
            } else {
                apiKeyContainer.classList.add('hidden');
            }
            
            console.log('Selected model:', selectedModel);
            
            // Enable/disable send button based on input
            updateSendButtonState();
        });
    });
    
    // Clear chat button
    clearChatButton.addEventListener('click', function() {
        // Clear all messages except the first one (system message)
        while (messagesContainer.childElementCount > 1) {
            messagesContainer.removeChild(messagesContainer.lastChild);
        }
    });
    
    // Handle API key option change
    useDefaultKeyRadio.addEventListener('change', function() {
        if (this.checked) {
            customKeyInput.classList.add('hidden');
            useDefaultApiKey = true;
            updateSendButtonState();
            
            // Show info notification about using default key
            showApiKeyNotification(`Using default API key for ${selectedModel.name}.`, true);
        }
    });

    useCustomKeyRadio.addEventListener('change', function() {
        if (this.checked) {
            customKeyInput.classList.remove('hidden');
            useDefaultApiKey = false;
            updateSendButtonState();
            
            // Hide notification
            hideApiKeyNotification();
        }
    });
    
    // API key input change
    apiKeyInput.addEventListener('input', updateSendButtonState);
    
    // Submit API Key button
    submitApiKeyButton.addEventListener('click', function() {
        if (useDefaultApiKey) {
            // Just mark as submitted when using default key
            currentApiKeySubmitted = true;
            apiKeyContainer.classList.add('hidden');
            updateSendButtonState();
        } else {
            const apiKey = apiKeyInput.value.trim();
            if (apiKey) {
                // Store the API key for this model
                modelApiKeys[selectedModel.id] = apiKey;
                currentApiKeySubmitted = true;
                
                // Hide the API key container
                apiKeyContainer.classList.add('hidden');
                // Update send button state
                updateSendButtonState();
            } else {
                showError('Please enter an API key');
            }
        }
    });
    
    // Load sources
    loadSources();
    
    // Handle "Select All" checkbox
    selectAllCheckbox.addEventListener('change', function() {
        const isChecked = this.checked;
        
        // Update all source checkboxes
        document.querySelectorAll('.source-checkbox').forEach(checkbox => {
            checkbox.checked = isChecked;
        });
        
        // Update selected sources
        updateSelectedSources();
    });
    
    // Function to update send button state
    function updateSendButtonState() {
        const hasText = userInput.value.trim().length > 0;
        const hasModel = selectedModel !== null;
        const hasApiKey = !selectedModel?.needsKey || 
                        useDefaultApiKey || 
                        (apiKeyInput.value.trim().length > 0 && !useDefaultApiKey);
        
        sendButton.disabled = !(hasText && hasModel && hasApiKey);
    }
    
    // Function to send message
    function sendMessage() {
        const message = userInput.value.trim();
        
        if (!message || !selectedModel) return;
        
        // Get the API key for the selected model
        let apiKey = null;
        let useDefaultKey = false;
        
        if (selectedModel.needsKey) {
            if (useDefaultApiKey) {
                // Use default API key
                useDefaultKey = true;
            } else if (currentApiKeySubmitted && modelApiKeys[selectedModel.id]) {
                // If key was submitted for this model, use the stored key
                apiKey = modelApiKeys[selectedModel.id];
            } else {
                // Otherwise use the current input value
                apiKey = apiKeyInput.value.trim();
                
                if (!apiKey) {
                    showError('Please enter an API key for ' + selectedModel.name);
                    return;
                }
            }
        }
        
        // Disable input and show loading
        userInput.disabled = true;
        sendButton.disabled = true;
        loadingIndicator.style.display = 'flex';
        errorMessage.classList.add('hidden');
        
        // Add user message to chat
        addMessage(message, 'user');
    
        // Clear input
        userInput.value = '';
        userInput.style.height = 'auto';
    
        // Call API
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message,
                model: selectedModel.id,
                api_key: apiKey,
                use_default_key: useDefaultKey,
                selected_source_ids: selectedSourceIds
            }),
        })
        .then(response => {
            console.log('Chat response status:', response.status);
            if (!response.ok) {
                // Handle HTTP error status codes
                return response.json().then(errorData => {
                    throw new Error(errorData.error || `Server error: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            // Hide loading
            loadingIndicator.style.display = 'none';
            
            if (data.success) {
                // Add AI response to chat with context data
                addMessage(data.response, 'assistant', data.context);
            } else {
                // Show error
                showError(data.error || 'An error occurred');
            }
            
            // Re-enable input
            userInput.disabled = false;
            updateSendButtonState();
        })
        .catch(error => {
            // Hide loading
            loadingIndicator.style.display = 'none';
            
            // Show error
            showError(error.message || 'Network error: Failed to get a response');
            
            // Re-enable input
            userInput.disabled = false;
            updateSendButtonState();
        });
    }
    
    // Function to add message to chat
    function addMessage(content, sender, context = null) {
    const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Create message content container
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Process markdown-like syntax in assistant messages
        if (sender === 'assistant') {
            // Handle code blocks
            content = content.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
            
            // Handle inline code
            content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
            
            // Handle bold text
            content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            
            // Handle italic text
            content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');
            
            // Handle links
            content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
            
            // Handle line breaks
            content = content.replace(/\n/g, '<br>');
            
            // Add context button if context is available
            if (context) {
                // Add the content to the content div
                contentDiv.innerHTML = content;
                
                // Create controls container
                const controlsDiv = document.createElement('div');
                controlsDiv.className = 'message-controls';
                
                // Create context toggle button
                const contextButton = document.createElement('button');
                contextButton.className = 'context-toggle-btn';
                contextButton.innerHTML = '<i class="fas fa-code"></i> Show Raw Context';
                
                // Create context container (hidden by default)
                const contextDiv = document.createElement('div');
                contextDiv.className = 'context-container hidden';
                contextDiv.innerHTML = `<pre>${JSON.stringify(context, null, 2)}</pre>`;
                
                // Add click handler for toggle button
                contextButton.addEventListener('click', () => {
                    contextDiv.classList.toggle('hidden');
                    contextButton.innerHTML = contextDiv.classList.contains('hidden') ? 
                        '<i class="fas fa-code"></i> Show Raw Context' : 
                        '<i class="fas fa-code-merge"></i> Hide Raw Context';
                });
                
                // Add elements to message
                controlsDiv.appendChild(contextButton);
                messageDiv.appendChild(contentDiv);
                messageDiv.appendChild(controlsDiv);
                messageDiv.appendChild(contextDiv);
            } else {
                contentDiv.innerHTML = content;
                messageDiv.appendChild(contentDiv);
            }
        } else {
            // For user messages, just handle line breaks
            content = content.replace(/\n/g, '<br>');
            contentDiv.innerHTML = content;
            messageDiv.appendChild(contentDiv);
        }
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Function to show error
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
        
        // Automatically hide error after 7 seconds
        setTimeout(() => {
            errorMessage.classList.add('hidden');
        }, 7000);
    }
    
    // Function to load sources
    function loadSources() {
        // Show loading indicator
        document.getElementById('sources-loading').style.display = 'flex';
        sourcesList.innerHTML = '';
        
        // Fetch sources from the API
        fetch('/get-sources')
            .then(response => response.json())
            .then(data => {
                // Hide loading indicator
                document.getElementById('sources-loading').style.display = 'none';
                
                if (data.sources && data.sources.length > 0) {
                    // Create sources list
                    sourcesList.innerHTML = data.sources.map(source => `
                        <li class="source-item">
                            <input type="checkbox" class="source-checkbox" data-source-id="${source.id}" checked>
                            <div class="source-info">
                                <div class="source-name">${source.name}</div>
                                <div class="source-meta">${getSourceTypeLabel(source.type)} - ${source.wordCount || 0} words</div>
                            </div>
                        </li>
                    `).join('');
                    
                    // Add event listeners to checkboxes
                    document.querySelectorAll('.source-checkbox').forEach(checkbox => {
                        checkbox.dataset.sourceId = checkbox.dataset.sourceId;
                        checkbox.addEventListener('change', updateSelectedSources);
                    });
                    
                    // Initialize selected sources
                    updateSelectedSources();
                    console.log('Initial selected sources after loading:', selectedSourceIds);
                    
                } else {
                    // Show message if no sources available
                    sourcesList.innerHTML = `
                        <li class="source-item">
                            <span class="source-name">No sources available. <a href="/conversation-upload">Add sources</a></span>
                        </li>
                    `;
                    console.warn('No sources found in data:', data);
                }
            })
            .catch(error => {
                console.error('Error loading sources:', error);
                sourcesList.innerHTML = `
                    <li class="source-item">
                        <span class="source-name">Error loading sources. <a href="/conversation-upload">Add sources</a></span>
                    </li>
                `;
            });
    }
    
    // Keep track of selected sources
    function updateSelectedSources() {
        const sourceCheckboxes = document.querySelectorAll('.source-checkbox');
        
        // Reset the array
        selectedSourceIds = [];
        
        // Update selected sources based on checkboxes
        sourceCheckboxes.forEach(cb => {
            if (cb.checked) {
                selectedSourceIds.push(cb.dataset.sourceId);
            }
        });
        
        // Update "Select All" checkbox state
        const allChecked = selectedSourceIds.length === sourceCheckboxes.length;
        const someChecked = selectedSourceIds.length > 0 && selectedSourceIds.length < sourceCheckboxes.length;
        
        selectAllCheckbox.checked = allChecked;
        selectAllCheckbox.indeterminate = someChecked;
        
        console.log('Updated selected sources:', selectedSourceIds);
    }
    
    // Helper function to get a user-friendly label for source types
    function getSourceTypeLabel(type) {
        switch(type) {
            case 'file': return 'Document';
            case 'link': return 'Website';
            case 'text': return 'Text';
            default: return type;
        }
    }
    
    // Select Ollama as default model if available
    const ollamaOption = document.querySelector('.model-option[data-model="ollama"]');
    if (ollamaOption) {
        ollamaOption.click();
    }

    // Function to show API key notification
    function showApiKeyNotification(message, isInfo = false) {
        apiKeyNotification.textContent = message;
        apiKeyNotification.classList.remove('hidden');
        
        if (isInfo) {
            apiKeyNotification.classList.add('info');
        } else {
            apiKeyNotification.classList.remove('info');
        }
    }

    // Function to hide API key notification
    function hideApiKeyNotification() {
        apiKeyNotification.classList.add('hidden');
    }

    // Function to check if default API key is available
    function checkDefaultApiKey(modelId) {
        fetch('/check-default-key', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: modelId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (!data.has_default_key) {
                // If no default key, disable default option and select custom
                useDefaultKeyRadio.disabled = true;
                useCustomKeyRadio.checked = true;
                customKeyInput.classList.remove('hidden');
                useDefaultApiKey = false;
                
                // Show a notification
                showApiKeyNotification(`No default API key available for ${selectedModel.name}. Please enter a custom key.`);
            } else {
                // Enable default option
                useDefaultKeyRadio.disabled = false;
                // Show a notification that default key is available
                showApiKeyNotification(`Default API key is available for ${selectedModel.name}.`, true);
            }
            
            // Update send button state
            updateSendButtonState();
        })
        .catch(error => {
            console.error('Error checking default API key:', error);
        });
    }
});