/**
 * SCOS Global Configuration
 * Centralized source of truth for backend REST and WebSocket connectivity.
 */
(function() {
    const PRODUCTION_REST_URL = 'https://scos-app.onrender.com';

    /**
     * Determines whether the current execution context is native Capacitor.
     */
    function isNativePlatform() {
        return !!(window.Capacitor && typeof window.Capacitor.isNativePlatform === 'function' && window.Capacitor.isNativePlatform());
    }

    /**
     * Determines the active backend REST base URL.
     * Order of precedence:
     * 1. Explicit override via localStorage.getItem('SCOS_BACKEND_URL') or window.SCOS_BACKEND_URL
     * 2. file:// protocol -> null (prevents silent fallback to production and logs diagnostic)
     * 3. Native Capacitor (Android APK) -> Default PRODUCTION_REST_URL
     * 4. Web browser over HTTP/HTTPS -> window.location.origin
     */
    function getBackendUrl() {
        // 1. Explicit developer override (useful for Android emulator 10.0.2.2, LAN IP, or testing)
        let overrideUrl = null;
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                overrideUrl = window.localStorage.getItem('SCOS_BACKEND_URL');
            } else if (typeof localStorage !== 'undefined') {
                overrideUrl = localStorage.getItem('SCOS_BACKEND_URL');
            }
        } catch (e) {
            // localStorage might be unavailable in restricted sandbox contexts
        }
        if (!overrideUrl && typeof window !== 'undefined' && typeof window.SCOS_BACKEND_URL === 'string' && window.SCOS_BACKEND_URL.trim() !== '') {
            overrideUrl = window.SCOS_BACKEND_URL;
        }

        if (overrideUrl && typeof overrideUrl === 'string' && overrideUrl.trim() !== '') {
            return overrideUrl.trim().replace(/\/+$/, '');
        }

        // 2. Direct file:// protocol check — fail safely with clear diagnostic
        if (window.location && window.location.protocol === 'file:') {
            console.error(
                "[SCOS Config Error] Running directly via 'file://' protocol is not supported for backend connectivity. " +
                "Please serve the frontend via FastAPI (e.g., http://localhost:8000/app/) or explicitly configure " +
                "localStorage.setItem('SCOS_BACKEND_URL', 'http://10.0.2.2:8000')."
            );
            return null;
        }

        // 3. Native Capacitor platform (Android APK)
        if (isNativePlatform()) {
            return PRODUCTION_REST_URL;
        }

        // 4. Standard web browser served over HTTP or HTTPS
        if (window.location && window.location.origin && window.location.origin !== 'null') {
            return window.location.origin;
        }

        console.warn("[SCOS Config] Unable to determine backend origin, defaulting to null.");
        return null;
    }

    /**
     * Constructs a WebSocket URL matching the exact host and port of the active REST backend.
     * @param {string} path - WebSocket endpoint path (e.g. '/api/ws/driver/1?token=xyz')
     */
    function getWsUrl(path) {
        const backend = getBackendUrl();
        if (!backend) {
            console.error("[SCOS Config] Cannot construct WebSocket URL because backend URL is not configured.");
            return null;
        }

        const normalizedPath = path.startsWith('/') ? path : '/' + path;

        // Try standard URL constructor
        const URLClass = (typeof URL !== 'undefined') ? URL : (typeof window !== 'undefined' ? window.URL : null);
        if (URLClass) {
            try {
                const parsed = new URLClass(backend);
                const wsProtocol = (parsed.protocol === 'https:') ? 'wss:' : 'ws:';
                return `${wsProtocol}//${parsed.host}${normalizedPath}`;
            } catch (e) {
                // fall through to regex parsing
            }
        }

        // Regex parser fallback (matches http(s)://host:port)
        const match = backend.match(/^(https?:\/\/)?([^/]+)/i);
        if (match) {
            const scheme = match[1] || 'http://';
            const host = match[2];
            const wsProtocol = scheme.toLowerCase().startsWith('https') ? 'wss:' : 'ws:';
            return `${wsProtocol}//${host}${normalizedPath}`;
        }

        return null;
    }

    window.SCOS_CONFIG = {
        PRODUCTION_REST_URL: PRODUCTION_REST_URL,
        isNativePlatform: isNativePlatform,
        getBackendUrl: getBackendUrl,
        getWsUrl: getWsUrl,
        setDevBackend: function(url) {
            if (url) {
                localStorage.setItem('SCOS_BACKEND_URL', url);
                console.log(`[SCOS Config] Backend URL set to: ${url}`);
            } else {
                localStorage.removeItem('SCOS_BACKEND_URL');
                console.log("[SCOS Config] Backend URL reset to default.");
            }
        }
    };
})();
