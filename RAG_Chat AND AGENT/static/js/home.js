document.addEventListener('DOMContentLoaded', function() {
    // Tab switching functionality
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Initial setup - remove animate-fade-in from all step items
    document.querySelectorAll('.step-item').forEach(item => {
        item.classList.remove('animate-fade-in');
    });
    
    // Add single animation to visible tab items on page load
    const initialActiveTabId = document.querySelector('.tab.active').getAttribute('data-tab') + '-tab';
    document.querySelectorAll(`#${initialActiveTabId} .step-item`).forEach((item, index) => {
        item.style.opacity = '0';
        setTimeout(() => {
            item.style.transition = 'opacity 0.3s ease';
            item.style.opacity = '1';
        }, index * 100);
    });
    
    // Handle tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            const tabContentEl = document.getElementById(tabId + '-tab');
            
            // Only proceed if this tab isn't already active
            if (!tab.classList.contains('active')) {
                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Hide all tab contents
                tabContents.forEach(content => {
                    content.classList.add('hidden');
                });
                
                // Show selected tab content
                tabContentEl.classList.remove('hidden');
                
                // Reset all step items in the new tab
                const stepItems = tabContentEl.querySelectorAll('.step-item');
                stepItems.forEach(item => {
                    item.style.opacity = '0';
                });
                
                // Animate step items with delay
                stepItems.forEach((item, index) => {
                    setTimeout(() => {
                        item.style.transition = 'opacity 0.3s ease';
                        item.style.opacity = '1';
                    }, index * 100);
                });
            }
        });
    });
});