document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const selectedSourcesList = document.getElementById('selected-sources');
    const sourceList = document.getElementById('source-list');
    const sourcesPanel = document.getElementById('sources-panel');
    const noSourcesMessage = document.getElementById('no-sources-message');
    const sourceCountEl = document.getElementById('source-count');
    const generateBtn = document.getElementById('generate-dataset');
    const previewPanel = document.getElementById('preview-panel');
    const qaPreview = document.getElementById('qa-preview');
    const qaCountDisplay = document.getElementById('qa-count-display');
    const modelOptions = document.querySelectorAll('.model-option');
    const apiKeyContainer = document.getElementById('api-key-container');
    const apiKeyInput = document.getElementById('api-key');
    const submitApiKeyButton = document.getElementById('submit-api-key');
    const queryInput = document.getElementById('query-input');
    const addQueryBtn = document.getElementById('add-query');
    const customQueriesList = document.getElementById('custom-queries');
    const includeAutoQueries = document.getElementById('include-auto-queries');
    const useDefaultKeyRadio = document.getElementById('use-default-key');
    const useCustomKeyRadio = document.getElementById('use-custom-key');
    const customKeyInput = document.getElementById('custom-key-input');
    const apiKeyNotification = document.getElementById('api-key-notification');
    
    // Variables
    let sources = [];
    let selectedModel = null;
    let customQueries = [];
    let modelApiKeys = {}; // Store API keys for different models
    let currentApiKeySubmitted = false; // Track if current API key has been submitted
    let useDefaultApiKey = true; // Default to using default API key
    
    // Helper function to show errors that auto-dismiss
    function showError(message, element) {
        // Clear any existing error messages first
        if (element) {
            const existingErrors = element.querySelectorAll('.error-message');
            existingErrors.forEach(err => err.remove());
        }
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            <p>${message}</p>
        `;
        
        // If an element is provided, append to that element
        if (element) {
            element.innerHTML = '';
            element.appendChild(errorDiv);
        }
        
        // Auto-hide after 7 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 7000);
        
        return errorDiv;
    }
    
    // Custom alert function with auto-dismiss
    function showAlert(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'custom-alert';
        alertDiv.innerHTML = `
            <div class="alert-content">
                <i class="fas fa-exclamation-circle"></i>
                <p>${message}</p>
            </div>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-hide after 7 seconds
        setTimeout(() => {
            alertDiv.classList.add('fade-out');
            setTimeout(() => {
                alertDiv.remove();
            }, 300); // Fade out transition
        }, 7000);
    }
    
    // Load existing sources when page loads
    loadSources();
    
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
                // Hide any notifications
                hideApiKeyNotification();
            }
            
            console.log('Selected model:', selectedModel);
            
            // Update generate button state
            updateGenerateButtonState();
        });
    });
    
    // API key input change
    apiKeyInput.addEventListener('input', updateGenerateButtonState);
    
    // Submit API Key button
    submitApiKeyButton.addEventListener('click', function() {
        if (useDefaultApiKey) {
            // Just mark as submitted when using default key
            currentApiKeySubmitted = true;
            apiKeyContainer.classList.add('hidden');
            updateGenerateButtonState();
        } else {
            const apiKey = apiKeyInput.value.trim();
            if (apiKey) {
                // Store the API key for this model
                modelApiKeys[selectedModel.id] = apiKey;
                currentApiKeySubmitted = true;
                
                // Hide the API key container
                apiKeyContainer.classList.add('hidden');
                // Update generate button state
                updateGenerateButtonState();
            } else {
                showAlert('Please enter an API key');
            }
        }
    });
    
    // Custom query handling
    addQueryBtn.addEventListener('click', () => {
        const query = queryInput.value.trim();
        if (query) {
            addCustomQuery(query);
            queryInput.value = '';
        }
    });
    
    // Add custom query function
    function addCustomQuery(query) {
        const queryId = Date.now().toString();
        customQueries.push({ id: queryId, text: query });
        
        const queryItem = document.createElement('div');
        queryItem.className = 'custom-query-item';
        queryItem.dataset.id = queryId;
        queryItem.innerHTML = `
            <div class="query-text">${query}</div>
            <button class="query-remove" data-id="${queryId}">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        customQueriesList.appendChild(queryItem);
        
        // Add event listener for remove button
        queryItem.querySelector('.query-remove').addEventListener('click', (e) => {
            const id = e.currentTarget.dataset.id;
            removeCustomQuery(id);
        });
    }
    
    // Remove custom query
    function removeCustomQuery(id) {
        customQueries = customQueries.filter(q => q.id !== id);
        
        const queryItem = document.querySelector(`.custom-query-item[data-id="${id}"]`);
        if (queryItem) {
            queryItem.remove();
        }
    }
    
    // Function to load sources from the server with better error handling
    function loadSources() {
        fetch('/get-sources')
            .then(response => response.json())
            .then(data => {
                console.log('Loaded sources:', data.sources);
                if (data.sources && data.sources.length > 0) {
                    // We have sources from the previous upload
                    sources = data.sources;
                    displaySources();
                    updateGenerateButtonState();
                } else {
                    // No sources found
                    selectedSourcesList.innerHTML = '';
                    sourceList.style.display = 'none';
                    noSourcesMessage.style.display = 'block';
                    generateBtn.disabled = true;
                }
            })
            .catch(error => {
                console.error('Error loading sources:', error);
                selectedSourcesList.innerHTML = '';
                const errorElement = showError('Failed to load sources. Please try again.', selectedSourcesList);
                errorElement.classList.add('text-center', 'p-3');
                generateBtn.disabled = true;
            });
    }
    
    // Display loaded sources
    function displaySources() {
        // Update count
        sourceCountEl.textContent = sources.length;
        
        // Update list
        selectedSourcesList.innerHTML = '';
        
        // Create items for each source
        sources.forEach(source => {
            const sourceItem = document.createElement('div');
            sourceItem.className = 'source-item';
            sourceItem.innerHTML = `
                <div class="source-icon">
                    <i class="${getSourceIcon(source.type)}"></i>
                </div>
                <div class="source-details">
                    <div class="source-name">${source.name}</div>
                    <div class="source-meta">${source.wordCount || '0'} words</div>
                </div>
            `;
            
            selectedSourcesList.appendChild(sourceItem);
        });
    }
    
    // Get icon based on source type
    function getSourceIcon(type) {
        switch(type) {
            case 'file':
                return 'fas fa-file-alt';
            case 'link':
                return 'fas fa-link';
            case 'text':
                return 'fas fa-align-left';
            default:
                return 'fas fa-file';
        }
    }
    
    // Function to update generate button state
    function updateGenerateButtonState() {
        const hasSources = sources && sources.length > 0;
        const hasModel = selectedModel !== null;
        const hasApiKey = !selectedModel?.needsKey || 
                         useDefaultApiKey || 
                         (apiKeyInput.value.trim().length > 0 && !useDefaultApiKey);
        
        generateBtn.disabled = !(hasSources && hasModel && hasApiKey);
    }
    
    // Generate dataset button
    generateBtn.addEventListener('click', function() {
        // Validate inputs
        if (!selectedModel) {
            showAlert('Please select a model');
            return;
        }
        
        if (!sources || sources.length === 0) {
            showAlert('Please add at least one source');
            return;
        }
        
        // Get settings
        const qaCount = parseInt(document.getElementById('qa-count').value, 10);
        const difficulty = document.getElementById('difficulty').value;
        // Format selector has been removed from HTML, defaulting to JSON
        const format = 'json';
        
        // Get API key if needed
        let apiKey = null;
        let useDefaultKey = false;
        
        if (selectedModel.needsKey) {
            if (useDefaultApiKey) {
                // Use default API key
                useDefaultKey = true;
            } else if (currentApiKeySubmitted && modelApiKeys[selectedModel.id]) {
                // Use submitted key
                apiKey = modelApiKeys[selectedModel.id];
            } else {
                // Get key from input
                apiKey = apiKeyInput.value.trim();
                
                if (!apiKey) {
                    showAlert('Please enter an API key');
                    return;
                }
            }
        }
        
        // Show loading indicator
        qaPreview.innerHTML = '';
        
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'loading-indicator';
        loadingIndicator.innerHTML = `
            <i class="fas fa-spinner fa-spin"></i>
            <span>Generating QA pairs...</span>
        `;
        
        qaPreview.appendChild(loadingIndicator);
        previewPanel.style.display = 'block';
        
        // Scroll to preview
        previewPanel.scrollIntoView({ behavior: 'smooth' });
        
        // Prepare data
        const requestData = {
            sources: sources,
            qaCount: qaCount,
            difficulty: difficulty,
            model: selectedModel.id,
            api_key: apiKey,
            use_default_key: useDefaultKey,
            customQueries: customQueries.map(q => q.text),
            includeAutoQueries: includeAutoQueries.checked
        };
        
        // Call the backend API
        fetch('/generate-qa-dataset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            console.log('Response status:', response.status);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Display the generated QA pairs
                displayQAPairs(data.qa_pairs);
            } else {
                // Show error with more details
                console.error('API Error:', data.error);
                qaPreview.innerHTML = '';
                const errorMsg = data.error || 'An error occurred while generating the dataset.';
                
                // Create simpler error messages for common issues
                let displayError = errorMsg;
                if (errorMsg.includes('invalid_api_key') || errorMsg.includes('Incorrect API key') || 
                    errorMsg.includes('invalid x-api-key') || errorMsg.includes('authentication_error')) {
                    displayError = `Invalid API key for ${selectedModel.name}. Please check your API key and try again.`;
                } else if (errorMsg.includes('timeout')) {
                    displayError = `The request timed out. Please try again later.`;
                } else if (errorMsg.includes('rate limit')) {
                    displayError = `Rate limit exceeded. Please wait a moment before trying again.`;
                }
                
                const errorElement = showError(displayError, qaPreview);
                
                // Only show the sources hint if the error is related to sources
                if (errorMsg.includes('sources') || errorMsg.includes('find content')) {
                    const hint = document.createElement('p');
                    hint.className = 'small-text';
                    hint.textContent = 'If sources can\'t be found, try going back to the upload page and re-processing your sources.';
                    errorElement.appendChild(hint);
                }
            }
            // Remove the loading indicator instead of hiding it
            const loadingElement = document.querySelector('.loading-indicator');
            if (loadingElement) {
                loadingElement.remove();
            }
            
            // Scroll to preview
            previewPanel.scrollIntoView({ behavior: 'smooth' });
        })
        .catch(error => {
            console.error('Error:', error);
            qaPreview.innerHTML = '';
            showError('Failed to connect to the server. Please try again later.', qaPreview);
            // Remove the loading indicator instead of hiding it
            const loadingElement = document.querySelector('.loading-indicator');
            if (loadingElement) {
                loadingElement.remove();
            }
        });
    });
    
    // Display QA pairs in the preview
    function displayQAPairs(pairs) {
        qaPreview.innerHTML = '';
        
        // Update count display
        qaCountDisplay.textContent = pairs.length;
        
        // Add each QA pair to the preview
        pairs.forEach((pair, index) => {
            const qaItem = document.createElement('div');
            qaItem.className = 'qa-pair';
            qaItem.innerHTML = `
                <div class="qa-question">Q${index+1}: ${pair.question}</div>
                <div class="qa-answer">A: ${pair.answer}</div>
                <div class="qa-source">Source: ${pair.source}</div>
            `;
            
            qaPreview.appendChild(qaItem);
        });
    }
    
    // Refresh preview button
    document.getElementById('refresh-preview').addEventListener('click', () => {
        // Similar to generate but without showing the preview panel again
        const qaCount = document.getElementById('qa-count').value;
        const difficulty = document.getElementById('difficulty').value;
        
        // Clear previous content
        qaPreview.innerHTML = '';
        
        // Create a new loading indicator each time
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'loading-indicator';
        loadingIndicator.innerHTML = `
            <i class="fas fa-spinner fa-spin"></i>
            <span>Generating QA pairs...</span>
        `;
        loadingIndicator.style.display = 'flex';
        
        // Add it to the preview
        qaPreview.appendChild(loadingIndicator);
        
        // Prepare source data for API
        const sourceData = sources.map(source => {
            return {
                id: source.id,
                name: source.name,
                type: source.type,
                url: source.url
            };
        });
        
        // Call the API again
        fetch('/generate-qa-dataset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sources: sourceData,
                qaCount: qaCount,
                difficulty: difficulty,
                model: selectedModel.id,
                api_key: selectedModel.needsKey ? apiKeyInput.value.trim() : null,
                customQueries: customQueries.map(q => q.text),
                includeAutoQueries: includeAutoQueries.checked
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayQAPairs(data.qa_pairs);
            } else {
                // Show error with more details
                console.error('API Error:', data.error);
                qaPreview.innerHTML = '';
                const errorMsg = data.error || 'An error occurred while generating the dataset.';
                
                // Create simpler error messages for common issues
                let displayError = errorMsg;
                if (errorMsg.includes('invalid_api_key') || errorMsg.includes('Incorrect API key') || 
                    errorMsg.includes('invalid x-api-key') || errorMsg.includes('authentication_error')) {
                    displayError = `Invalid API key for ${selectedModel.name}. Please check your API key and try again.`;
                } else if (errorMsg.includes('timeout')) {
                    displayError = `The request timed out. Please try again later.`;
                } else if (errorMsg.includes('rate limit')) {
                    displayError = `Rate limit exceeded. Please wait a moment before trying again.`;
                }
                
                const errorElement = showError(displayError, qaPreview);
                
                // Only show the sources hint if the error is related to sources
                if (errorMsg.includes('sources') || errorMsg.includes('find content')) {
                    const hint = document.createElement('p');
                    hint.className = 'small-text';
                    hint.textContent = 'If sources can\'t be found, try going back to the upload page and re-processing your sources.';
                    errorElement.appendChild(hint);
                }
            }
            // Remove the loading indicator instead of hiding it
            const loadingElement = document.querySelector('.loading-indicator');
            if (loadingElement) {
                loadingElement.remove();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            qaPreview.innerHTML = '';
            showError('Failed to connect to the server. Please try again later.', qaPreview);
            // Remove the loading indicator instead of hiding it
            const loadingElement = document.querySelector('.loading-indicator');
            if (loadingElement) {
                loadingElement.remove();
            }
        });
    });
    
    // Export buttons
    document.getElementById('export-json').addEventListener('click', () => {
        exportDataset('json');
    });
    
    document.getElementById('export-csv').addEventListener('click', () => {
        exportDataset('csv');
    });
    
    document.getElementById('export-txt').addEventListener('click', () => {
        exportDataset('txt');
    });
    
    // Export dataset function
    function exportDataset(format) {
        const qaPairs = [];
        
        // Collect all QA pairs from the preview
        document.querySelectorAll('.qa-pair').forEach(pair => {
            const question = pair.querySelector('.qa-question').textContent.substring(4); // Remove "Q1: " prefix
            const answer = pair.querySelector('.qa-answer').textContent.substring(3); // Remove "A: " prefix
            const source = pair.querySelector('.qa-source').textContent.substring(8); // Remove "Source: " prefix
            
            qaPairs.push({ question, answer, source });
        });
        
        if (qaPairs.length === 0) {
            showAlert('No QA pairs to export. Please generate the dataset first.');
            return;
        }
        
        let content = '';
        let filename = `qa_dataset_${Date.now()}`;
        let mimeType = '';
        
        // Format content based on selected format
        switch(format) {
            case 'json':
                content = JSON.stringify(qaPairs, null, 2);
                filename += '.json';
                mimeType = 'application/json';
                break;
                
            case 'csv':
                content = 'Question,Answer,Source\n';
                qaPairs.forEach(pair => {
                    content += `"${pair.question}","${pair.answer}","${pair.source}"\n`;
                });
                filename += '.csv';
                mimeType = 'text/csv';
                break;
                
            case 'txt':
                qaPairs.forEach((pair, index) => {
                    content += `Q${index+1}: ${pair.question}\n`;
                    content += `A: ${pair.answer}\n`;
                    content += `Source: ${pair.source}\n\n`;
                });
                filename += '.txt';
                mimeType = 'text/plain';
                break;
        }
        
        // Create download link
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        
        // Clean up
        URL.revokeObjectURL(url);
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

    // Handle API key option change
    useDefaultKeyRadio.addEventListener('change', function() {
        if (this.checked) {
            customKeyInput.classList.add('hidden');
            useDefaultApiKey = true;
            updateGenerateButtonState();
            
            // Show info notification about using default key
            showApiKeyNotification(`Using default API key for ${selectedModel.name}.`, true);
        }
    });

    useCustomKeyRadio.addEventListener('change', function() {
        if (this.checked) {
            customKeyInput.classList.remove('hidden');
            useDefaultApiKey = false;
            updateGenerateButtonState();
            
            // Hide notification
            hideApiKeyNotification();
        }
    });

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
            
            // Update generate button state
            updateGenerateButtonState();
        })
        .catch(error => {
            console.error('Error checking default API key:', error);
        });
    }
});