/**
 * Types & API endpoints for the processed-materials feature.
 * Kept in its own module so existing api/types.ts and api/endpoints.ts stay untouched.
 */
import { api } from './client';
import type { Paginated, UUID } from './types';

// ── Types ─────────────────────────────────────────────────────────────────
export interface ProcessedRecipeItem {
  id: UUID;
  processed_material?: UUID;
  raw_material: UUID | null;
  raw_material_name?: string;
  raw_material_unit?: string;
  raw_material_unit_cost?: string;
  sub_processed_material: UUID | null;
  sub_processed_material_name?: string;
  sub_processed_material_unit?: string;
  sub_processed_material_unit_cost?: string;
  quantity: string;
}

export interface ProcessedUsage {
  id: UUID;
  product?: UUID;
  product_name?: string;
  product_sku?: string;
  processed_material?: UUID;
  processed_material_name?: string;
  processed_material_unit?: string;
  processed_material_unit_cost?: string;
  quantity: string;
}

export interface ProcessedMaterial {
  id: UUID;
  sku: string;
  name: string;
  unit: string;
  yield_per_batch: string;
  unit_cost: string;
  overhead_pct: string;
  shelf_life_hours: number;
  reorder_threshold: string;
  notes: string;
  is_active: boolean;
  recipe_items: ProcessedRecipeItem[];
  used_in_products: ProcessedUsage[];
  stock_quantity: string;
  is_low: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProcessedMaterialStock {
  id: UUID;
  processed_material: UUID;
  item_name: string;
  item_sku: string;
  item_unit: string;
  item_unit_cost: string;
  quantity: string;
  reorder_threshold: string;
  is_low: boolean;
}

export interface ProcessedMaterialStockMovement {
  id: UUID;
  stock: UUID;
  item_name: string;
  item_sku: string;
  item_unit: string;
  reason: string;
  reason_display: string;
  quantity_delta: string;
  balance_after: string;
  reference: string;
  note: string;
  created_by: UUID | null;
  created_by_name: string | null;
  created_at: string;
}

export interface ProcessedMaterialBatch {
  id: UUID;
  processed_material: UUID;
  processed_material_name: string;
  processed_material_sku: string;
  processed_material_unit: string;
  batches: string;
  quantity_produced: string;
  cost: string;
  scheduled_for: string;
  completed_at: string | null;
  notes: string;
  created_by: UUID | null;
  created_by_name: string | null;
  created_at: string;
}

// ── Endpoints ────────────────────────────────────────────────────────────
const ROOT = '/processed-materials';

export const processedMaterials = {
  list: (params: Record<string, unknown> = {}) =>
    api.get<Paginated<ProcessedMaterial>>(`${ROOT}/materials/`, { params }).then((r) => r.data),
  get: (id: string) =>
    api.get<ProcessedMaterial>(`${ROOT}/materials/${id}/`).then((r) => r.data),
  create: (data: Partial<ProcessedMaterial>) =>
    api.post<ProcessedMaterial>(`${ROOT}/materials/`, data).then((r) => r.data),
  update: (id: string, data: Partial<ProcessedMaterial>) =>
    api.patch<ProcessedMaterial>(`${ROOT}/materials/${id}/`, data).then((r) => r.data),
  remove: (id: string) => api.delete(`${ROOT}/materials/${id}/`),

  recipes: {
    list: (params: Record<string, unknown> = {}) =>
      api.get<Paginated<ProcessedRecipeItem>>(`${ROOT}/recipes/`, { params }).then((r) => r.data),
    create: (data: Partial<ProcessedRecipeItem>) =>
      api.post<ProcessedRecipeItem>(`${ROOT}/recipes/`, data).then((r) => r.data),
    update: (id: string, data: Partial<ProcessedRecipeItem>) =>
      api.patch<ProcessedRecipeItem>(`${ROOT}/recipes/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`${ROOT}/recipes/${id}/`),
  },

  usages: {
    list: (params: Record<string, unknown> = {}) =>
      api.get<Paginated<ProcessedUsage>>(`${ROOT}/usages/`, { params }).then((r) => r.data),
    create: (data: Partial<ProcessedUsage>) =>
      api.post<ProcessedUsage>(`${ROOT}/usages/`, data).then((r) => r.data),
    update: (id: string, data: Partial<ProcessedUsage>) =>
      api.patch<ProcessedUsage>(`${ROOT}/usages/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`${ROOT}/usages/${id}/`),
  },

  stock: {
    list: (params: Record<string, unknown> = {}) =>
      api.get<Paginated<ProcessedMaterialStock>>(`${ROOT}/stock/`, { params }).then((r) => r.data),
    low: () =>
      api.get<Paginated<ProcessedMaterialStock>>(`${ROOT}/stock/low-stock/`).then((r) => r.data),
    adjust: (data: {
      processed_material: string;
      quantity_delta: number;
      note?: string;
      reference?: string;
    }) =>
      api.post(`${ROOT}/stock/adjust/`, data).then((r) => r.data),
    writeOff: (data: {
      processed_material: string;
      quantity: number;
      note?: string;
      reference?: string;
    }) =>
      api.post(`${ROOT}/stock/write-off/`, data).then((r) => r.data),
  },

  movements: {
    list: (params: Record<string, unknown> = {}) =>
      api.get<Paginated<ProcessedMaterialStockMovement>>(`${ROOT}/movements/`, { params })
        .then((r) => r.data),
  },

  batches: {
    list: (params: Record<string, unknown> = {}) =>
      api.get<Paginated<ProcessedMaterialBatch>>(`${ROOT}/batches/`, { params })
        .then((r) => r.data),
    produce: (data: {
      processed_material: string;
      batches: number;
      scheduled_for?: string;
      notes?: string;
    }) => api.post<ProcessedMaterialBatch>(`${ROOT}/batches/produce/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`${ROOT}/batches/${id}/`),
  },
};
