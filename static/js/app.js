/**
 * ANPR Management System - Main JavaScript
 * Common functionality and utilities
 */

// Global configuration
const CONFIG = {
    API_BASE_URL: '/api',
    REFRESH_INTERVAL: 30000, // 30 seconds
    DEBOUNCE_DELAY: 300,
    PAGINATION_LIMIT: 50
};

// Global state
const AppState = {
    currentUser: null,
    isLoading: false,
    notifications: []
};

// Utility functions
const Utils = {
    /**
     * Debounce function to limit API calls
     */
    debounce: function(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    },

    /**
     * Format date for display
     */
    formatDate: function(dateString, includeTime = false) {
        const date = new Date(dateString);
        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        };
        
        if (includeTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
        }
        
        return date.toLocaleDateString('en-US', options);
    },

    /**
     * Format datetime for display
     */
    formatDateTime: function(dateString) {
        return this.formatDate(dateString, true);
    },

    /**
     * Get relative time (e.g., "2 hours ago")
     */
    getRelativeTime: function(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        if (diffInSeconds < 60) return 'Just now';
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
        if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)} days ago`;
        
        return this.formatDate(dateString);
    },

    /**
     * Validate license plate format
     */
    validateLicensePlate: function(plate) {
        // Basic validation - can be enhanced for specific formats
        const pattern = /^[A-Z0-9\-\s]{2,10}$/i;
        return pattern.test(plate.trim());
    },

    /**
     * Generate random ID
     */
    generateId: function() {
        return 'id_' + Math.random().toString(36).substr(2, 9);
    },

    /**
     * Copy text to clipboard
     */
    copyToClipboard: function(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text);
            this.showNotification('Copied to clipboard', 'success');
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showNotification('Copied to clipboard', 'success');
        }
    },

    /**
     * Show notification (can be enhanced with a proper toast library)
     */
    showNotification: function(message, type = 'info', duration = 3000) {
        // Simple alert for now - can be enhanced with toast notifications
        console.log(`${type.toUpperCase()}: ${message}`);
        
        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        toast.style.top = '20px';
        toast.style.right = '20px';
        toast.style.zIndex = '9999';
        toast.style.minWidth = '300px';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-dismiss after duration
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, duration);
    },

    /**
     * Handle API errors
     */
    handleApiError: function(error, defaultMessage = 'An error occurred') {
        console.error('API Error:', error);
        
        let message = defaultMessage;
        if (error.response) {
            // Server responded with error
            message = error.response.data.detail || error.response.data.message || defaultMessage;
        } else if (error.request) {
            // Network error
            message = 'Network error. Please check your connection.';
        }
        
        this.showNotification(message, 'danger');
    },

    /**
     * Show loading state
     */
    showLoading: function(element) {
        if (element) {
            element.innerHTML = `
                <div class="text-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;
        }
        AppState.isLoading = true;
    },

    /**
     * Hide loading state
     */
    hideLoading: function() {
        AppState.isLoading = false;
    },

    /**
     * Confirm action with user
     */
    confirm: function(message, title = 'Confirm Action') {
        return new Promise((resolve) => {
            // Simple confirm for now - can be enhanced with a modal
            const result = window.confirm(`${title}\n\n${message}`);
            resolve(result);
        });
    },

    /**
     * Export data to CSV
     */
    exportToCSV: function(data, filename = 'export.csv') {
        if (!data || data.length === 0) {
            this.showNotification('No data to export', 'warning');
            return;
        }
        
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => 
                headers.map(header => 
                    JSON.stringify(row[header] || '')
                ).join(',')
            )
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        this.showNotification(`Exported ${data.length} records`, 'success');
    }
};

// API helpers
const API = {
    /**
     * Make API request with common headers and error handling
     */
    request: async function(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        try {
            const response = await fetch(url, defaultOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            Utils.handleApiError(error);
            throw error;
        }
    },

    /**
     * GET request
     */
    get: function(endpoint, params = {}) {
        const url = new URL(`${CONFIG.API_BASE_URL}${endpoint}`, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                url.searchParams.append(key, params[key]);
            }
        });
        return this.request(url.toString());
    },

    /**
     * POST request
     */
    post: function(endpoint, data = {}) {
        return this.request(`${CONFIG.API_BASE_URL}${endpoint}`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT request
     */
    put: function(endpoint, data = {}) {
        return this.request(`${CONFIG.API_BASE_URL}${endpoint}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE request
     */
    delete: function(endpoint) {
        return this.request(`${CONFIG.API_BASE_URL}${endpoint}`, {
            method: 'DELETE'
        });
    }
};

// Form helpers
const FormHelper = {
    /**
     * Serialize form data to object
     */
    serializeForm: function(formElement) {
        const formData = new FormData(formElement);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            // Handle checkboxes
            if (formElement.querySelector(`[name="${key}"]`).type === 'checkbox') {
                data[key] = formElement.querySelector(`[name="${key}"]`).checked;
            } else {
                data[key] = value || null;
            }
        }
        
        return data;
    },

    /**
     * Reset form with default values
     */
    resetForm: function(formElement, defaults = {}) {
        formElement.reset();
        
        // Set default values
        Object.keys(defaults).forEach(key => {
            const field = formElement.querySelector(`[name="${key}"]`);
            if (field) {
                if (field.type === 'checkbox') {
                    field.checked = defaults[key];
                } else {
                    field.value = defaults[key];
                }
            }
        });
    },

    /**
     * Validate form fields
     */
    validateForm: function(formElement) {
        const errors = [];
        const requiredFields = formElement.querySelectorAll('[required]');
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                errors.push(`${field.labels[0]?.textContent || field.name} is required`);
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
            }
        });
        
        return errors;
    }
};

// Navigation helpers
const Navigation = {
    /**
     * Update active navigation item
     */
    updateActiveNav: function() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
        
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === currentPath || (href !== '/' && currentPath.startsWith(href))) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    },

    /**
     * Go to page
     */
    goTo: function(url) {
        window.location.href = url;
    }
};

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Update active navigation
    Navigation.updateActiveNav();
    
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Initialize popovers
    const popovers = document.querySelectorAll('[data-bs-toggle="popover"]');
    popovers.forEach(popover => {
        new bootstrap.Popover(popover);
    });
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K for search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('#searchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal.show');
            openModals.forEach(modal => {
                bootstrap.Modal.getInstance(modal)?.hide();
            });
        }
    });
    
    // Handle form submissions with loading states
    document.addEventListener('submit', function(e) {
        const form = e.target;
        if (form.tagName === 'FORM') {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
            }
        }
    });
    
    console.log('ANPR Management System initialized');
});

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    Utils.showNotification('An unexpected error occurred', 'danger');
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    Utils.showNotification('An unexpected error occurred', 'danger');
});

// Export utilities for use in other files
window.Utils = Utils;
window.API = API;
window.FormHelper = FormHelper;
window.Navigation = Navigation;
window.CONFIG = CONFIG; 