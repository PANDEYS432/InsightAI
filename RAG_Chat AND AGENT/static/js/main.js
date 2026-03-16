// Global state management
const state = {
    extractedContent: null,
    selectedModel: null,
    apiKey: null,
    theme: localStorage.getItem('theme') || 'light'
};

// Utility functions
function showLoading(show = true) {
    const loader = document.getElementById('loadingIndicator');
    if (loader) {
        loader.classList.toggle('hidden', !show);
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        ${message}
        <button onclick="this.parentElement.remove()" class="close-btn">
            <i class="fas fa-times"></i>
        </button>
    `;
    document.querySelector('.container').prepend(errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
}

function toggleContent() {
    const content = document.getElementById('extractedContent');
    const toggleBtn = document.querySelector('.toggle-btn i');
    if (content) {
        content.classList.toggle('hidden');
        toggleBtn.classList.toggle('fa-chevron-down');
        toggleBtn.classList.toggle('fa-chevron-up');
    }
}

function setExtractedContent(content) {
    state.extractedContent = content;
    localStorage.setItem('extractedContent', content);
    const contentElement = document.getElementById('extractedContent');
    if (contentElement) {
        contentElement.textContent = content;
        document.getElementById('contentPreview').classList.remove('hidden');
    }
}

function proceedToModelSelection() {
    if (!state.extractedContent) {
        showError('Please extract content first');
        return;
    }
    window.location.href = '/select-model';
}

// Theme toggle functionality
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = themeToggle.querySelector('i');
    
    // Set initial theme from localStorage
    if (state.theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeIcon.classList.remove('fa-sun');
        themeIcon.classList.add('fa-moon');
    }
    
    // Toggle theme on button click
    themeToggle.addEventListener('click', () => {
        // Toggle between light and dark
        const newTheme = state.theme === 'light' ? 'dark' : 'light';
        
        // Update HTML attribute
        document.documentElement.setAttribute('data-theme', newTheme);
        
        // Update icon
        if (newTheme === 'dark') {
            themeIcon.classList.remove('fa-sun');
            themeIcon.classList.add('fa-moon');
        } else {
            themeIcon.classList.remove('fa-moon');
            themeIcon.classList.add('fa-sun');
        }
        
        // Save to state and localStorage
        state.theme = newTheme;
        localStorage.setItem('theme', newTheme);
        
        // Show notification
        showNotification(`${newTheme.charAt(0).toUpperCase() + newTheme.slice(1)} theme enabled`, 'info',
        2000);
    });
}

// Main JavaScript file for the Dataset Generator application

document.addEventListener('DOMContentLoaded', function() {
    // Initialize mobile navigation
    initMobileNav();
    
    // Add smooth scrolling to all links
    initSmoothScroll();
    
    // Initialize any tooltips
    initTooltips();
    
    // Initialize theme toggle
    initThemeToggle();
});

/**
 * Initialize mobile navigation functionality
 */
function initMobileNav() {
    const navLinks = document.querySelector('.nav-links');
    const menuToggle = document.createElement('button');
    menuToggle.className = 'menu-toggle';
    menuToggle.innerHTML = '<i class="fas fa-bars"></i>';
    menuToggle.setAttribute('aria-label', 'Toggle navigation menu');
    
    // Insert the menu toggle button after the brand
    const navBrand = document.querySelector('.nav-brand');
    if (navBrand && !document.querySelector('.menu-toggle')) {
        navBrand.parentNode.insertBefore(menuToggle, navBrand.nextSibling);
    }
    
    // Toggle menu visibility when the button is clicked
    menuToggle.addEventListener('click', function() {
        navLinks.classList.toggle('active');
        // Change icon based on menu state
        const icon = this.querySelector('i');
        if (navLinks.classList.contains('active')) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-times');
        } else {
            icon.classList.remove('fa-times');
            icon.classList.add('fa-bars');
        }
    });
    
    // Close menu when a link is clicked
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function() {
            if (window.innerWidth <= 768) {
                navLinks.classList.remove('active');
                const icon = menuToggle.querySelector('i');
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });
    });
}

/**
 * Add smooth scrolling to all links
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Initialize tooltips
 */
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseenter', function() {
            const tooltipText = this.getAttribute('data-tooltip');
            
            const tooltipElement = document.createElement('div');
            tooltipElement.className = 'tooltip';
            tooltipElement.textContent = tooltipText;
            
            document.body.appendChild(tooltipElement);
            
            const rect = this.getBoundingClientRect();
            tooltipElement.style.top = rect.bottom + 10 + 'px';
            tooltipElement.style.left = rect.left + (rect.width / 2) - (tooltipElement.offsetWidth / 2) + 'px';
            tooltipElement.style.opacity = '1';
        });
        
        tooltip.addEventListener('mouseleave', function() {
            const tooltipElement = document.querySelector('.tooltip');
            if (tooltipElement) {
                tooltipElement.remove();
            }
        });
    });
}

/**
 * Format date to a readable string
 * @param {Date} date - The date to format
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('en-US', options);
}

/**
 * Show a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, warning, info)
 * @param {number} duration - How long to show the notification in ms
 */
function showNotification(message, type = 'info', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-icon">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 
                              type === 'error' ? 'exclamation-circle' : 
                              type === 'warning' ? 'exclamation-triangle' : 
                              'info-circle'}"></i>
        </div>
        <div class="notification-content">${message}</div>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;
    
    document.body.appendChild(notification);
    
    // Add CSS to notification
    Object.assign(notification.style, {
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        backgroundColor: type === 'success' ? '#d4edda' :
                         type === 'error' ? '#f8d7da' :
                         type === 'warning' ? '#fff3cd' : '#d1ecf1',
        color: type === 'success' ? '#155724' :
               type === 'error' ? '#721c24' :
               type === 'warning' ? '#856404' : '#0c5460',
        padding: '15px 20px',
        borderRadius: '8px',
        boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        alignItems: 'center',
        maxWidth: '350px',
        zIndex: '9999',
        transform: 'translateY(100px)',
        opacity: '0',
        transition: 'all 0.3s ease'
    });
    
    // Show notification with animation
    setTimeout(() => {
        notification.style.transform = 'translateY(0)';
        notification.style.opacity = '1';
    }, 10);
    
    // Close notification on click
    notification.querySelector('.notification-close').addEventListener('click', () => {
        removeNotification(notification);
    });
    
    // Auto remove after duration
    setTimeout(() => {
        removeNotification(notification);
    }, duration);
}

/**
 * Remove notification with animation
 * @param {HTMLElement} notification - The notification element to remove
 */
function removeNotification(notification) {
    notification.style.transform = 'translateY(100px)';
    notification.style.opacity = '0';
    
    setTimeout(() => {
        notification.remove();
    }, 300);
}