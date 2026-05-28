/**
 * API 端点函数集合。
 *
 * 按模块分组:
 *   - 3D生成: textTo3D / imageTo3D / batchTextTo3D / getGenerationStatus
 *   - 修复:   autoRepair / analyzeDefects / getDefects
 *   - 资产:   listAssets / getAsset / deleteAsset / getDownloadUrl
 *   - 任务:   listTasks / getTask / retryTask
 *   - 日志:   reportLog / listLogs
 *   - 统计:   getStatsOverview
 */
import apiClient from "./client";

// ---- 3D 生成 ----

/** 提交文生3D任务 */
export const textTo3D = (data: { prompt: string; negative_prompt?: string; style?: string; skip_optimization?: boolean }) =>
  apiClient.post("/generate/text-to-3d", data);

/** 提交图生3D任务（FormData上传图片） */
export const imageTo3D = (file: File, style?: string) => {
  const form = new FormData();
  form.append("file", file);
  if (style) form.append("style", style);
  return apiClient.post("/generate/image-to-3d", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

/** 批量提交文生3D任务 */
export const batchTextTo3D = (data: { prompts: string[]; negative_prompt?: string; style?: string; skip_optimization?: boolean }) =>
  apiClient.post("/generate/batch-text-to-3d", data);

/** 轮询生成任务状态（前端每3秒调用一次） */
export const getGenerationStatus = (assetId: string) =>
  apiClient.get(`/generate/status/${assetId}`);

// ---- 模型修复 ----

/** 对指定资产执行自动缺陷检测 + 轻修复 */
export const autoRepair = (assetId: string) =>
  apiClient.post("/repair/auto-repair", { asset_id: assetId });

/** 使用Qwen3 LLM深度分析缺陷 */
export const analyzeDefects = (assetId: string) =>
  apiClient.post("/repair/analyze-defects", { asset_id: assetId });

/** 查询指定资产的缺陷详情列表 */
export const getDefects = (assetId: string) =>
  apiClient.get(`/repair/defects/${assetId}`);

// ---- 资产管理 ----

/** 分页查询资产列表（支持status/asset_type过滤） */
export const listAssets = (params?: Record<string, unknown>) =>
  apiClient.get("/assets/", { params });

/** 获取单个资产详情 */
export const getAsset = (assetId: string) =>
  apiClient.get(`/assets/${assetId}`);

/** 删除资产及其关联文件 */
export const deleteAsset = (assetId: string) =>
  apiClient.delete(`/assets/${assetId}`);

/** 生成多格式下载URL（直接拼接，不经过axios） */
export const getDownloadUrl = (assetId: string, format: string) =>
  `/api/v1/assets/${assetId}/download/${format}`;

// ---- 任务管理 ----

/** 查询任务列表（支持status/task_type过滤） */
export const listTasks = (params?: Record<string, unknown>) =>
  apiClient.get("/tasks/", { params });

/** 获取单个任务详情 */
export const getTask = (taskId: string) =>
  apiClient.get(`/tasks/${taskId}`);

/** 重试失败的任务（仅支持text_to_3d/image_to_3d） */
export const retryTask = (taskId: string) =>
  apiClient.post(`/tasks/${taskId}/retry`);

// ---- 日志管理 ----

/** 前端上报用户行为日志 */
export const reportLog = (data: { session_id: string; action: string; page?: string; asset_id?: string; details?: Record<string, unknown> }) =>
  apiClient.post("/logs/report", data);

/** 查询用户行为日志列表 */
export const listLogs = (params?: Record<string, unknown>) =>
  apiClient.get("/logs/list", { params });

// ---- 统计仪表盘 ----

/** 获取仪表盘概览统计数据 */
export const getStatsOverview = () =>
  apiClient.get("/stats/overview");
