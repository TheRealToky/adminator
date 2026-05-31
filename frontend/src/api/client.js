import axios from 'axios';
const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const ACCESS_KEY = 'adminator.access';
const REFRESH_KEY = 'adminator.refresh';
export const tokens = {
    getAccess() { return localStorage.getItem(ACCESS_KEY); },
    getRefresh() { return localStorage.getItem(REFRESH_KEY); },
    setTokens(access, refresh) {
        localStorage.setItem(ACCESS_KEY, access);
        localStorage.setItem(REFRESH_KEY, refresh);
    },
    clear() {
        localStorage.removeItem(ACCESS_KEY);
        localStorage.removeItem(REFRESH_KEY);
    },
};
export const api = axios.create({
    baseURL,
    timeout: 30_000,
    headers: { 'Content-Type': 'application/json' },
});
api.interceptors.request.use((config) => {
    const token = tokens.getAccess();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
// One-flight refresh queue.
let refreshing = null;
async function refreshAccessToken() {
    const refresh = tokens.getRefresh();
    if (!refresh)
        return null;
    try {
        const res = await axios.post(`${baseURL}/auth/refresh/`, { refresh });
        const newAccess = res.data.access;
        const newRefresh = res.data.refresh ?? refresh;
        tokens.setTokens(newAccess, newRefresh);
        return newAccess;
    }
    catch {
        tokens.clear();
        return null;
    }
}
api.interceptors.response.use((response) => response, async (error) => {
    const original = error.config;
    if (error.response?.status === 401 &&
        original &&
        !original._retry &&
        !original.url?.includes('/auth/login') &&
        !original.url?.includes('/auth/refresh')) {
        original._retry = true;
        if (!refreshing)
            refreshing = refreshAccessToken();
        const newToken = await refreshing;
        refreshing = null;
        if (newToken) {
            original.headers = { ...(original.headers || {}), Authorization: `Bearer ${newToken}` };
            return api.request(original);
        }
        window.location.assign('/login');
    }
    return Promise.reject(error);
});
export function extractErrorMessage(err, fallback = 'Something went wrong.') {
    if (axios.isAxiosError(err)) {
        const data = err.response?.data;
        if (typeof data === 'string')
            return data;
        if (data && typeof data === 'object') {
            if (typeof data.detail === 'string')
                return data.detail;
            const firstKey = Object.keys(data)[0];
            if (firstKey) {
                const v = data[firstKey];
                if (Array.isArray(v) && v.length > 0)
                    return `${firstKey}: ${v[0]}`;
                if (typeof v === 'string')
                    return `${firstKey}: ${v}`;
            }
        }
        return err.message || fallback;
    }
    return fallback;
}
