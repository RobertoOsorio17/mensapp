// Configurar CSRF token para todas las peticiones AJAX
function setupCSRF() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    // Configurar el token CSRF para todas las peticiones fetch
    window.fetchWithCSRF = function(url, options = {}) {
        options.headers = {
            ...options.headers,
            'X-CSRFToken': csrfToken
        };
        return fetch(url, options);
    };

    // Configurar para Socket.IO
    if (typeof io !== 'undefined') {
        const socket = io({
            transportOptions: {
                polling: {
                    extraHeaders: {
                        'X-CSRFToken': csrfToken
                    }
                }
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', setupCSRF);
