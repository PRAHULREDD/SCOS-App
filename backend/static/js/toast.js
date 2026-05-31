/**
 * Global Toast Notification System
 * Replaces native window.alert with smooth animated snackbars.
 */
window.showToast = function(message, type = 'info', duration = 3000) {
    // Determine colors based on type
    let bgClass = 'bg-surface-container-highest text-on-surface';
    let icon = 'info';
    let iconColor = 'text-primary';
    
    if (type === 'success') {
        bgClass = 'bg-primary-container text-on-primary-container';
        icon = 'check_circle';
        iconColor = 'text-on-primary-container';
    } else if (type === 'error') {
        bgClass = 'bg-error-container text-on-error-container';
        icon = 'error';
        iconColor = 'text-error';
    } else if (type === 'warning') {
        bgClass = 'bg-secondary-container text-on-secondary-container';
        icon = 'warning';
        iconColor = 'text-secondary';
    }

    // Create container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-24 left-1/2 transform -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none w-[90%] max-w-sm';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border border-outline-variant/20 transform transition-all duration-300 translate-y-10 opacity-0 ${bgClass}`;
    
    toast.innerHTML = `
        <span class="material-symbols-outlined ${iconColor}" style="font-variation-settings: 'FILL' 1;">${icon}</span>
        <span class="font-body-md text-sm font-medium flex-1">${message}</span>
    `;

    container.appendChild(toast);

    // Trigger entrance animation
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-10', 'opacity-0');
            toast.classList.add('translate-y-0', 'opacity-100');
        });
    });

    // Remove after duration
    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-10', 'opacity-0');
        setTimeout(() => {
            toast.remove();
        }, 300); // Wait for transition
    }, duration);
};
