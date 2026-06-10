/**
 * Mobile Device Integration for Capacitor
 */
document.addEventListener('DOMContentLoaded', () => {
    // Only execute if running natively on a mobile device via Capacitor
    if (window.Capacitor && window.Capacitor.isNativePlatform()) {
        const { App } = window.Capacitor.Plugins;
        
        // Handle hardware back button on Android
        App.addListener('backButton', ({ canGoBack }) => {
            if (canGoBack) {
                window.history.back();
            } else {
                // If on the root screen, exit the app
                App.exitApp();
            }
        });

        // Add class to body for mobile specific styling if needed
        document.body.classList.add('is-native-mobile');
    }
});
