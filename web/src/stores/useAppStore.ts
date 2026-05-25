import { create } from "zustand";

interface AppState {
  sessionId: string;
  collapsed: boolean;
  toggleCollapsed: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  sessionId: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36),
  collapsed: false,
  toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),
}));
