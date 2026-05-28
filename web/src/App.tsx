/**
 * 应用根组件 — 路由定义。
 *
 * 路由结构:
 *   AppLayout（侧边栏 + 顶栏布局）
 *     ├── /            → Dashboard（仪表盘/统计）
 *     ├── /generate    → Generate（3D生成）
 *     ├── /repair      → Repair（模型修复）
 *     ├── /assets      → Assets（资产管理）
 *     └── /logs        → Logs（操作日志/任务记录）
 */
import { Routes, Route } from "react-router-dom";
import AppLayout from "./components/Layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import Generate from "./pages/Generate";
import Repair from "./pages/Repair";
import Assets from "./pages/Assets";
import Logs from "./pages/Logs";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/generate" element={<Generate />} />
        <Route path="/repair" element={<Repair />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/logs" element={<Logs />} />
      </Route>
    </Routes>
  );
}
