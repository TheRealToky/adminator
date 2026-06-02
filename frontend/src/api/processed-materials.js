/**
 * Types & API endpoints for the processed-materials feature.
 * Kept in its own module so existing api/types.ts and api/endpoints.ts stay untouched.
 */
import { api } from './client';
// ── Endpoints ────────────────────────────────────────────────────────────
const ROOT = '/processed-materials';
export const processedMaterials = {
    list: (params = {}) => api.get(`${ROOT}/materials/`, { params }).then((r) => r.data),
    get: (id) => api.get(`${ROOT}/materials/${id}/`).then((r) => r.data),
    create: (data) => api.post(`${ROOT}/materials/`, data).then((r) => r.data),
    update: (id, data) => api.patch(`${ROOT}/materials/${id}/`, data).then((r) => r.data),
    remove: (id) => api.delete(`${ROOT}/materials/${id}/`),
    recipes: {
        list: (params = {}) => api.get(`${ROOT}/recipes/`, { params }).then((r) => r.data),
        create: (data) => api.post(`${ROOT}/recipes/`, data).then((r) => r.data),
        update: (id, data) => api.patch(`${ROOT}/recipes/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`${ROOT}/recipes/${id}/`),
    },
    usages: {
        list: (params = {}) => api.get(`${ROOT}/usages/`, { params }).then((r) => r.data),
        create: (data) => api.post(`${ROOT}/usages/`, data).then((r) => r.data),
        update: (id, data) => api.patch(`${ROOT}/usages/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`${ROOT}/usages/${id}/`),
    },
    stock: {
        list: (params = {}) => api.get(`${ROOT}/stock/`, { params }).then((r) => r.data),
        low: () => api.get(`${ROOT}/stock/low-stock/`).then((r) => r.data),
        adjust: (data) => api.post(`${ROOT}/stock/adjust/`, data).then((r) => r.data),
        writeOff: (data) => api.post(`${ROOT}/stock/write-off/`, data).then((r) => r.data),
    },
    movements: {
        list: (params = {}) => api.get(`${ROOT}/movements/`, { params })
            .then((r) => r.data),
    },
    batches: {
        list: (params = {}) => api.get(`${ROOT}/batches/`, { params })
            .then((r) => r.data),
        produce: (data) => api.post(`${ROOT}/batches/produce/`, data).then((r) => r.data),
        remove: (id) => api.delete(`${ROOT}/batches/${id}/`),
    },
};
