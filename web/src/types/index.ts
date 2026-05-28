/**
 * 全局TypeScript类型定义。
 *
 * 对应后端 Pydantic schemas，用于前端API响应类型标注。
 * 命名规范: 保持与后端JSON字段一致（snake_case），通过axios自动序列化。
 */

/** 资产完整信息（对应 AssetResponse） */
export interface AssetInfo {
  id: string;
  name: string;
  asset_type: "text_to_3d" | "image_to_3d";
  status: "generating" | "generated" | "processing" | "processed" | "failed";
  source_prompt?: string;
  face_count?: number;
  vertex_count?: number;
  api_provider?: string;
  glb_path?: string;
  fbx_path?: string;
  obj_path?: string;
  preview_image_path?: string;
  tags?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

/** 任务信息（对应 TaskResponse） */
export interface TaskInfo {
  id: string;
  asset_id?: string;
  task_type: string;
  status: string;
  progress: number;           // 0.0 ~ 1.0
  input_params?: Record<string, unknown>;
  output_result?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
}

/** 缺陷信息（对应 getDefects 返回的 defects[0]） */
export interface DefectInfo {
  id: string;
  type: string;               // 缺陷类型标识（non_manifold_edge / degenerate_face / inverted_normal 等）
  level: "mild" | "moderate" | "severe";
  description: string;
  repairable: boolean;        // 是否可自动修复
  repaired: boolean;          // 是否已修复
  tutorial?: string;          // LLM生成的修复教程文本
}

/** 生成状态查询结果（对应 GenerationStatusResponse，前端轮询用） */
export interface GenerationStatus {
  asset_id: string;
  status: string;
  progress: number;
  model_url?: string;         // 模型GLB文件相对URL
  preview_url?: string;       // 预览图PNG相对URL
  face_count?: number;
  error_message?: string;
}

/** 文生3D返回结果（对应 TextTo3DResponse，含LLM优化/审核信息） */
export interface TextTo3DResult {
  task_id: string;
  asset_id: string;
  status: string;
  message: string;
  original_prompt?: string;           // 用户原始输入
  optimized_prompt?: string;          // LLM优化后的正负向提示词
  optimized_negative_prompt?: string;
  audit_result?: Record<string, unknown>;  // LLM安全审核结果
}

/** 批量文生3D返回结果 */
export interface BatchTextTo3DResult {
  batch_id: string;
  total: number;
  tasks: TextTo3DResult[];
}

/** 仪表盘统计数据（对应 stats/overview 接口返回） */
export interface StatsOverview {
  total_assets: number;
  total_tasks: number;
  total_defects: number;
  generation_success_rate: number;   // 近7天生成成功率(%)
  auto_repair_rate: number;          // 近7天自动修复成功率(%)
  avg_defects_per_model: number;     // 平均每模型缺陷数
  top_defect_types: { type: string; count: number }[];
  assets_by_status: Record<string, number>;
  tasks_by_type: Record<string, number>;
}
