import apiClient from "./client";

// 3D 生成
export const textTo3D = (data: { prompt: string; negative_prompt?: string; style?: string }) =>
  apiClient.post("/generate/text-to-3d", data);

export const imageTo3D = (file: File, style?: string) => {
  const form = new FormData();
  form.append("file", file);
  if (style) form.append("style", style);
  return apiClient.post("/generate/image-to-3d", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getGenerationStatus = (assetId: string) =>
  apiClient.get(`/generate/status/${assetId}`);

// 修复
export const autoRepair = (assetId: string) =>
  apiClient.post("/repair/auto-repair", { asset_id: assetId });

export const analyzeDefects = (assetId: string) =>
  apiClient.post("/repair/analyze-defects", { asset_id: assetId });

export const getDefects = (assetId: string) =>
  apiClient.get(`/repair/defects/${assetId}`);

// 资产
export const listAssets = (params?: Record<string, unknown>) =>
  apiClient.get("/assets/", { params });

export const getAsset = (assetId: string) =>
  apiClient.get(`/assets/${assetId}`);

export const deleteAsset = (assetId: string) =>
  apiClient.delete(`/assets/${assetId}`);

export const getDownloadUrl = (assetId: string, format: string) =>
  `/api/v1/assets/${assetId}/download/${format}`;

// 任务
export const listTasks = (params?: Record<string, unknown>) =>
  apiClient.get("/tasks/", { params });

export const getTask = (taskId: string) =>
  apiClient.get(`/tasks/${taskId}`);

export const retryTask = (taskId: string) =>
  apiClient.post(`/tasks/${taskId}/retry`);

// 日志
export const reportLog = (data: { session_id: string; action: string; page?: string; asset_id?: string; details?: Record<string, unknown> }) =>
  apiClient.post("/logs/report", data);
