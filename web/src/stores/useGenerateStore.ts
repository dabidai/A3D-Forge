/**
 * 生成页面局部状态管理（Zustand）。
 *
 * 管理文生3D表单状态:
 *   - prompt / negativePrompt: 用户输入的正负向提示词
 *   - style: 目标风格（realistic / cartoon / low_poly / sculpture）
 *   - generating: 是否正在生成（控制按钮loading状态）
 *
 * 注意: 此store为共享状态，跨组件使用需注意重置时机。
 */
import { create } from "zustand";

interface GenerateState {
  prompt: string;
  negativePrompt: string;
  style: string;
  generating: boolean;
  setPrompt: (v: string) => void;
  setNegativePrompt: (v: string) => void;
  setStyle: (v: string) => void;
  setGenerating: (v: boolean) => void;
  /** 重置所有表单字段为默认值 */
  reset: () => void;
}

const defaults = { prompt: "", negativePrompt: "", style: "realistic", generating: false };

export const useGenerateStore = create<GenerateState>((set) => ({
  ...defaults,
  setPrompt: (v) => set({ prompt: v }),
  setNegativePrompt: (v) => set({ negativePrompt: v }),
  setStyle: (v) => set({ style: v }),
  setGenerating: (v) => set({ generating: v }),
  reset: () => set(defaults),
}));
