document.addEventListener('DOMContentLoaded', function() {
    // Clear sources on page load
    clearSources();
    
    // DOM elements
    const fileInput = document.getElementById('file-input');
    const fileDropZone = document.getElementById('file-drop-zone');
    const selectedSourcesList = document.getElementById('selected-sources');
    const sourceList = document.getElementById('source-list');
    const sourceCountEl = document.getElementById('source-count');
    const linkInput = document.getElementById('link-input');
    const addLinkBtn = document.getElementById('add-link');
    const textInput = document.getElementById('text-input');
    const addTextBtn = document.getElementById('add-text');
    const processBtn = document.getElementById('process-sources');
    const tabs = document.querySelectorAll('.upload-tab');
    const panels = {
        file: document.getElementById('file-panel'),
        link: document.getElementById('link-panel'),
        text: document.getElementById('text-panel')
    };

    // Setup tabs
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            
            // Update active tab
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Show/hide panels
            Object.keys(panels).forEach(key => {
                panels[key].style.display = key === tabId ? 'block' : 'none';
            });
        });
    });

    // Variables
    let sources = [];
    let sourceCount = 0;
    const MAX_SOURCES = 5;
    let rawMarkdownContent = '';

    // File Upload Handling
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        fileDropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        fileDropZone.addEventListener(eventName, () => {
            fileDropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        fileDropZone.addEventListener(eventName, () => {
            fileDropZone.classList.remove('dragover');
        });
    });

    fileDropZone.addEventListener('drop', handleDrop);
    fileDropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFiles);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles({ target: { files } });
    }

    function handleFiles(e) {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            const extension = file.name.split('.').pop().toLowerCase();
            if (['pdf', 'txt', 'md'].includes(extension)) {
                if (sourceCount < MAX_SOURCES) {
                    addSource('file', file.name, file);
                } else {
                    showError('Maximum source limit of 5 reached');
                }
            } else {
                showError(`File type .${extension} is not supported. Please upload PDF, TXT, or MD files.`);
            }
        });
    }

    // Add Link Handling
    addLinkBtn.addEventListener('click', () => {
        const link = linkInput.value.trim();
        if (link) {
            try {
                new URL(link);
                if (sourceCount < MAX_SOURCES) {
                    addSource('link', link, link);
                    linkInput.value = '';
                } else {
                    showError('Maximum source limit of 5 reached');
                }
            } catch {
                showError('Please enter a valid URL');
            }
        }
    });

    // Add Text Handling
    addTextBtn.addEventListener('click', () => {
        const text = textInput.value.trim();
        if (text) {
            if (sourceCount < MAX_SOURCES) {
                addSource('text', 'Text source ' + (sourceCount + 1), text);
                textInput.value = '';
            } else {
                showError('Maximum source limit of 5 reached');
            }
        }
    });

    // Add Source
    async function addSource(type, name, content) {
        try {
            let extractedContent;
            
            if (type === 'file') {
                // Handle file upload
                const formData = new FormData();
                formData.append('file', content);
                
                const response = await fetch('/upload-document', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.error || 'Failed to upload file');
                }
                
                extractedContent = await response.json();
            } 
            else if (type === 'link') {
                // Handle URL processing
                const response = await fetch('/process-url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ url: content })
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    if (data.robots_txt_error) {
                        showError(`Access to ${content} is restricted by robots.txt rules`);
                        return;
                    }
                    throw new Error(data.error || 'Failed to process URL');
                }
                
                extractedContent = await response.json();
            } 
            else if (type === 'text') {
                // Handle direct text input
                const response = await fetch('/process-text', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ text: content })
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.error || 'Failed to process text');
                }
                
                extractedContent = await response.json();
            }

            if (!extractedContent || !extractedContent.content) {
                throw new Error('No content extracted from source');
            }

            // Store the extracted content
            sources.push({ 
                type, 
                name, 
                content: extractedContent.content,
                wordCount: extractedContent.word_count || 0,
                url: type === 'link' ? content : undefined  // Add URL for link sources
            });
            
            sourceCount++;
            updateSourceList();
            
            // Show success message
            showNotification(`Added: ${name}`, 'success');
            
        } catch (error) {
            console.error('Error processing source:', error);
            showError(error.message || 'An error occurred while processing the source');
        }
    }

    // Update Source List with word count
    function updateSourceList() {
        sourceCountEl.textContent = sourceCount;
        
        if (sources.length > 0) {
            sourceList.style.display = 'block';
            selectedSourcesList.innerHTML = sources.map((source, index) => `
                <div class="source-item-upload">
                    <div class="source-icon-upload">
                        <i class="fas ${getSourceIcon(source.type)}"></i>
                    </div>
                    <div class="source-details">
                        <span class="source-name-upload">${source.name}</span>
                        <span class="source-meta">${source.wordCount} words</span>
                    </div>
                    <div class="source-actions">
                        <button class="action-btn delete" onclick="removeSource(${index})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            sourceList.style.display = 'none';
        }
        updateProcessButton();
    }

    function getSourceIcon(type) {
        switch(type) {
            case 'file': return 'fa-file-alt';
            case 'link': return 'fa-link';
            case 'text': return 'fa-align-left';
            default: return 'fa-file';
        }
    }

    // Remove Source
    window.removeSource = function(index) {
        sources.splice(index, 1);
        sourceCount--;
        updateSourceList();
    };

    // Add notification function
    function showNotification(message, type = 'info') {
        const notif = document.createElement('div');
        notif.className = `notification notification-${type} animate-fade-in`;
        notif.innerHTML = `
            <div class="notification-icon">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 
                                type === 'error' ? 'exclamation-circle' : 
                                type === 'warning' ? 'exclamation-triangle' : 
                                'info-circle'}"></i>
            </div>
            <div class="notification-content">${message}</div>
        `;
        
        document.body.appendChild(notif);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notif.style.opacity = '0';
            setTimeout(() => notif.remove(), 300);
        }, 3000);
    }

    // Add error function
    function showError(message) {
        showNotification(message, 'error');
    }

    // Update Process Button State
    function updateProcessButton() {
        processBtn.disabled = sources.length === 0;
    }

    // Process sources
    processBtn.addEventListener('click', async () => {
        try {
            // Prepare source data for processing
            const sourceData = sources.map(source => ({
                id: source.id,
                type: source.type,
                name: source.name,
                content: source.content,
                wordCount: source.wordCount,
                url: source.url  // Include the URL for link sources
            }));
            
            // Only proceed if we have sources
            if (sourceData.length === 0) {
                throw new Error('No sources to process');
            }
            
            // Show loading state
            processBtn.disabled = true;
            processBtn.innerHTML = '<i class="fas fa-spin fa-spinner"></i> Processing...';
            
            // Send sources for processing
            const response = await fetch('/process-sources', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ sources: sourceData })
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to process sources');
            }
            
            const result = await response.json();
            
            if (result.success) {
                // Show success message
                showNotification('Sources processed successfully', 'success');
                
                // Show preview of combined extracted content
                const combinedContent = sources.map(source => {
                    return `### ${source.name}\n\n${source.content}\n\n`;
                }).join('---\n\n');
                
                // Store raw markdown for toggling
                rawMarkdownContent = combinedContent;
                
                // Show raw markdown content
                const extractedContent = document.getElementById('extracted-content');
                extractedContent.innerHTML = '';
                
                const pre = document.createElement('pre');
                pre.className = 'raw-markdown-content';
                pre.textContent = rawMarkdownContent;
                
                extractedContent.appendChild(pre);
                
                // Display the preview section
                const previewSection = document.getElementById('preview-section');
                previewSection.style.display = 'block';
                
                // Scroll to preview section
                previewSection.scrollIntoView({ behavior: 'smooth' });
            } else {
                throw new Error('Failed to process sources');
            }
        } catch (error) {
            console.error('Error processing sources:', error);
            showError(error.message || 'An error occurred while processing the sources');
        } finally {
            // Reset button state
            processBtn.disabled = false;
            processBtn.innerHTML = '<i class="fas fa-cog"></i> Process Sources';
        }
    });

    // Close preview button handler
    const closePreviewBtn = document.getElementById('close-preview');
    closePreviewBtn.addEventListener('click', () => {
        document.getElementById('preview-section').style.display = 'none';
    });

    // Continue button
    const continueBtn = document.getElementById('continue-btn');
    continueBtn.addEventListener('click', () => {
        // Make a POST request to set 'ready' flag in the session
        fetch('/ready-for-conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ready: true })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Redirect to the conversation page
                window.location.href = '/conversation';
            } else {
                showError('Error preparing conversation: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error setting ready state:', error);
            showError('Failed to prepare for conversation');
        });
    });

    // Generate Dataset button
    const generateDatasetBtn = document.getElementById('generate-dataset-btn');
    generateDatasetBtn.addEventListener('click', () => {
        // Make a POST request to set 'ready' flag in the session
        fetch('/ready-for-conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ready: true })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Redirect to the dataset generation page
                window.location.href = '/dataset';
            } else {
                showError('Error preparing sources: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error setting ready state:', error);
            showError('Failed to prepare sources for dataset generation');
        });
    });

    // Function to clear sources
    function clearSources() {
        fetch('/clear-sources', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('Sources cleared:', data);
            // Reset UI elements
            sources = [];
            sourceCount = 0;
            updateSourceList();
        })
        .catch(error => {
            console.error('Error clearing sources:', error);
        });
    }
    });