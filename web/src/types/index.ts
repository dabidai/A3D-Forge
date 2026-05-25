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

export interface TaskInfo {
  id: string;
  asset_id?: string;
  task_type: string;
  status: string;
  progress: number;
  input_params?: Record<string, unknown>;
  output_result?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
}

export interface DefectInfo {
  id: string;
  type: string;
  level: "mild" | "moderate" | "severe";
  description: string;
  repairable: boolean;
  repaired: boolean;
  tutorial?: string;
}

export interface GenerationStatus {
  asset_id: string;
  status: string;
  progress: number;
  model_url?: string;
  preview_url?: string;
  face_count?: number;
  error_message?: string;
}
