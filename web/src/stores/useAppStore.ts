/**
 * 全局应用状态管理（Zustand）。
 *
 * 管理:
 *   - sessionId:  浏览器会话标识（crypto.randomUUID()），用于关联用户行为日志
 *   - collapsed:  侧边栏折叠状态
 *   - logAction(): 快捷行为日志上报方法（封装 reportLog API 调用）
 */
import { create } from "zustand";
import { reportLog } from "@/api/endpoints";

interface AppState {
  sessionId: string;
  collapsed: boolean;
  toggleCollapsed: () => void;
  /** 上报用户行为日志到后端（静默失败，不影响主流程） */
  logAction: (action: string, page: string, assetId?: string, details?: Record<string, unknown>) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  sessionId: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36),
  collapsed: false,
  toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),
  logAction: (action, page, assetId, details) => {
    reportLog({
      session_id: get().sessionId,
      action,
      page,
      asset_id: assetId,
      details,
    }).catch(() => {});  // 静默失败，不阻塞UI操作
  },
}));
