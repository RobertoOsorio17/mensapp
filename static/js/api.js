// Configuración global para fetch
const API = {
    csrfToken: null,
    
    init() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (!metaTag) {
            console.error('CSRF token meta tag no encontrado');
            return;
        }
        this.csrfToken = metaTag.getAttribute('content');
    },

    async fetch(url, options = {}) {
        if (!this.csrfToken) {
            this.init();
        }

        const defaultOptions = {
            headers: {
                'X-CSRFToken': this.csrfToken,
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            ...options
        };

        try {
            const response = await fetch(url, defaultOptions);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `Error HTTP: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error en la petición:', error);
            throw error;
        }
    },

    // Métodos específicos para amigos
    friends: {
        async getList() {
            return API.fetch('/friends/list');
        },
        async getRequests() {
            return API.fetch('/friends/requests');
        },
        async accept(friendId) {
            return API.fetch(`/friends/accept_friend/${friendId}`, {
                method: 'POST'
            });
        },
        async reject(friendId) {
            return API.fetch(`/friends/reject_friend/${friendId}`, {
                method: 'POST'
            });
        },
        async add(username) {
            return API.fetch('/friends/', {
                method: 'POST',
                body: JSON.stringify({ friend_username: username })
            });
        }
    },

    // Métodos específicos para chat
    chat: {
        async sendMessage(friendId, content) {
            return API.fetch(`/chat/send/${friendId}`, {
                method: 'POST',
                body: JSON.stringify({ content })
            });
        },
        async getHistory(friendId) {
            return API.fetch(`/chat/history/${friendId}`);
        }
    }
};

// Inicializar API cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => API.init());
