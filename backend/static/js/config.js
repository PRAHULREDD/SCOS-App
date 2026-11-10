/**
 * SCOS Global Configuration
 * Centralized source of truth for backend REST and WebSocket connectivity
 * across Web and Android Mobile (Capacitor) applications.
 */
(function() {
    const PRODUCTION_REST_URL = 'https://scos-app.onrender.com';
    const DEFAULT_EMULATOR_URL = 'http://10.0.2.2:8000';

    /**
     * Determines whether the current execution context is native Capacitor.
     */
    function isNativePlatform() {
        return !!(window.Capacitor && typeof window.Capacitor.isNativePlatform === 'function' && window.Capacitor.isNativePlatform());
    }

    /**
     * Validates that a resolved URL string is well-formed with HTTP/HTTPS protocol.
     */
    function isValidUrl(urlString) {
        if (!urlString || typeof urlString !== 'string') return false;
        try {
            const parsed = new URL(urlString);
            return parsed.protocol === 'http:' || parsed.protocol === 'https:';
        } catch (e) {
            return /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(urlString.trim());
        }
    }

    /**
     * Determines the active backend REST base URL.
     * Order of precedence:
     * 1. Explicit override via localStorage.getItem('SCOS_BACKEND_URL') or window.SCOS_BACKEND_URL
     * 2. Standard web browser served over HTTP/HTTPS -> window.location.origin
     * 3. file:// protocol -> null (prevents silent fallback to production and logs diagnostic)
     * 4. Native Capacitor platform (Android APK):
     *    a. Configured SCOS_ENV ('emulator' -> 10.0.2.2:8000, 'device' -> SCOS_DEV_SERVER_URL, 'production' -> Render)
     *    b. Default fallback -> PRODUCTION_REST_URL
     */
    function getBackendUrl() {
        // 1. Explicit developer override (highest precedence, universal for Web and Mobile)
        let overrideUrl = null;
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                overrideUrl = window.localStorage.getItem('SCOS_BACKEND_URL');
            } else if (typeof localStorage !== 'undefined') {
                overrideUrl = localStorage.getItem('SCOS_BACKEND_URL');
            }
        } catch (e) {
            // localStorage might be restricted
        }
        if (!overrideUrl && typeof window !== 'undefined' && typeof window.SCOS_BACKEND_URL === 'string' && window.SCOS_BACKEND_URL.trim() !== '') {
            overrideUrl = window.SCOS_BACKEND_URL;
        }

        if (overrideUrl && typeof overrideUrl === 'string' && overrideUrl.trim() !== '') {
            const cleanOverride = overrideUrl.trim().replace(/\/+$/, '');
            if (isValidUrl(cleanOverride)) {
                return cleanOverride;
            }
            console.error(`[SCOS Config Error] Invalid override backend URL: "${overrideUrl}". Must be http(s)://host[:port]`);
        }

        // 2. Standard web browser served over HTTP or HTTPS (always uses the hosting FastAPI origin)
        if (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin !== 'null' && window.location.protocol !== 'file:') {
            if (!isNativePlatform()) {
                return window.location.origin;
            }
        }

        // 3. Direct file:// protocol check — fail safely with clear diagnostic
        if (typeof window !== 'undefined' && window.location && window.location.protocol === 'file:') {
            console.error(
                "[SCOS Config Error] Running directly via 'file://' protocol is not supported for backend connectivity. " +
                "Please serve the frontend via FastAPI (e.g., http://localhost:8000/app/) or explicitly configure " +
                "localStorage.setItem('SCOS_BACKEND_URL', 'http://10.0.2.2:8000')."
            );
            return null;
        }

        // 4. Native Capacitor platform (Android APK / Emulator)
        if (isNativePlatform()) {
            let env = 'auto';
            try {
                env = (typeof localStorage !== 'undefined' && localStorage.getItem('SCOS_ENV')) ||
                      (typeof window !== 'undefined' && window.SCOS_ENV) ||
                      'auto';
            } catch (e) {}

            if (env === 'emulator') {
                const emuUrl = (typeof localStorage !== 'undefined' && localStorage.getItem('SCOS_EMULATOR_URL')) || DEFAULT_EMULATOR_URL;
                return emuUrl.trim().replace(/\/+$/, '');
            }

            if (env === 'device' || env === 'lan') {
                const lanUrl = typeof localStorage !== 'undefined' ? localStorage.getItem('SCOS_DEV_SERVER_URL') : null;
                if (lanUrl && isValidUrl(lanUrl)) {
                    return lanUrl.trim().replace(/\/+$/, '');
                }
                console.warn("[SCOS Config] SCOS_ENV is 'device'/'lan' but SCOS_DEV_SERVER_URL is not set. Falling back to emulator host.");
                return DEFAULT_EMULATOR_URL;
            }

            if (env === 'production') {
                return PRODUCTION_REST_URL;
            }

            // 'auto' mode on native: default to PRODUCTION_REST_URL
            return PRODUCTION_REST_URL;
        }

        console.warn("[SCOS Config] Unable to determine backend origin, defaulting to null.");
        return null;
    }

    /**
     * Constructs a WebSocket URL matching the exact host and port of the active REST backend.
     * @param {string} path - WebSocket endpoint path (e.g. '/ws/driver/1?token=xyz')
     */
    function getWsUrl(path) {
        const backend = getBackendUrl();
        if (!backend) {
            console.error("[SCOS Config] Cannot construct WebSocket URL because backend URL is not configured.");
            return null;
        }

        const normalizedPath = path.startsWith('/') ? path : '/' + path;

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

        const match = backend.match(/^(https?:\/\/)?([^/]+)/i);
        if (match) {
            const scheme = match[1] || 'http://';
            const host = match[2];
            const wsProtocol = scheme.toLowerCase().startsWith('https') ? 'wss:' : 'ws:';
            return `${wsProtocol}//${host}${normalizedPath}`;
        }

        return null;
    }

    /**
     * Returns structured diagnostic information about current client platform and resolved URLs.
     */
    function getDiagnosticInfo() {
        const backend = getBackendUrl();
        const isNative = isNativePlatform();
        let env = 'auto';
        let override = null;
        try {
            if (typeof localStorage !== 'undefined') {
                env = localStorage.getItem('SCOS_ENV') || 'auto';
                override = localStorage.getItem('SCOS_BACKEND_URL');
            }
        } catch (e) {}

        return {
            platform: isNative ? 'Capacitor Android Native' : 'Standard Web Browser',
            isNative: isNative,
            configuredEnv: env,
            activeBackendUrl: backend,
            activeWsUrl: backend ? getWsUrl('/ws/driver/1') : null,
            hasExplicitOverride: !!override,
            overrideUrl: override,
            windowOrigin: (typeof window !== 'undefined' && window.location) ? window.location.origin : 'N/A',
            status: backend ? 'RESOLVED' : 'UNRESOLVED'
        };
    }

    window.SCOS_CONFIG = {
        PRODUCTION_REST_URL: PRODUCTION_REST_URL,
        DEFAULT_EMULATOR_URL: DEFAULT_EMULATOR_URL,
        isNativePlatform: isNativePlatform,
        isValidUrl: isValidUrl,
        getBackendUrl: getBackendUrl,
        getWsUrl: getWsUrl,
        getDiagnosticInfo: getDiagnosticInfo,
        setDevBackend: function(url) {
            if (url) {
                localStorage.setItem('SCOS_BACKEND_URL', url);
                console.log(`[SCOS Config] Backend URL set to: ${url}`);
            } else {
                localStorage.removeItem('SCOS_BACKEND_URL');
                console.log("[SCOS Config] Backend URL reset to default.");
            }
        },
        setEnvironment: function(envName, customUrl) {
            if (envName) {
                localStorage.setItem('SCOS_ENV', envName);
                if (customUrl) {
                    if (envName === 'emulator') {
                        localStorage.setItem('SCOS_EMULATOR_URL', customUrl);
                    } else if (envName === 'device' || envName === 'lan') {
                        localStorage.setItem('SCOS_DEV_SERVER_URL', customUrl);
                    }
                }
                console.log(`[SCOS Config] Environment set to: ${envName}`);
            } else {
                localStorage.removeItem('SCOS_ENV');
                console.log("[SCOS Config] Environment reset to auto.");
            }
        }
    };

    // Diagnostic heartbeat log on startup
    const diag = getDiagnosticInfo();
    console.log(`[SCOS Config] Initialized for ${diag.platform} -> Backend: ${diag.activeBackendUrl} (${diag.status})`);
})();
