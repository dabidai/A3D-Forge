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
