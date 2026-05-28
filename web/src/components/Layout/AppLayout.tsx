/**
 * 应用主布局组件：侧边栏 + 顶栏 + 内容区。
 *
 * 功能:
 *   - Ant Design 侧边栏导航（5个菜单项）
 *   - 可折叠侧边栏（图标按钮切换）
 *   - 页面路由切换时自动上报 page_view 行为日志
 *   - 响应式内容区通过 <Outlet /> 渲染子路由
 */
import { useState, useEffect, useRef } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, theme } from "antd";
import {
  DashboardOutlined,
  PlusCircleOutlined,
  ToolOutlined,
  FolderOutlined,
  FileTextOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { useAppStore } from "@/stores/useAppStore";

const { Header, Sider, Content } = Layout;

/** 页面路径 → 中文名称映射 */
const pageNames: Record<string, string> = {
  "/": "仪表盘",
  "/generate": "3D生成",
  "/repair": "模型修复",
  "/assets": "资产管理",
  "/logs": "操作日志",
};

/** 侧边栏菜单项配置 */
const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/generate", icon: <PlusCircleOutlined />, label: "3D 生成" },
  { key: "/repair", icon: <ToolOutlined />, label: "模型修复" },
  { key: "/assets", icon: <FolderOutlined />, label: "资产管理" },
  { key: "/logs", icon: <FileTextOutlined />, label: "操作日志" },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const logAction = useAppStore((s) => s.logAction);
  const prevPage = useRef(location.pathname);

  // 页面切换时上报行为日志
  useEffect(() => {
    if (location.pathname !== prevPage.current) {
      logAction("page_view", pageNames[location.pathname] || location.pathname);
      prevPage.current = location.pathname;
    }
  }, [location.pathname, logAction]);

  return (
    <Layout className="app-layout" style={{ minHeight: "100vh" }}>
      {/* 侧边栏 */}
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark">
        {/* 品牌Logo区 */}
        <div style={{
          height: 64, display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontSize: collapsed ? 14 : 18, fontWeight: 700,
          borderBottom: "1px solid rgba(255,255,255,0.1)",
          whiteSpace: "nowrap", overflow: "hidden",
        }}>
          {collapsed ? "A3D" : "AI 3D 平台"}
        </div>
        {/* 导航菜单 — 当前路由高亮 */}
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>

      <Layout>
        {/* 顶栏 */}
        <Header style={{
          padding: "0 24px", background: token.colorBgContainer,
          display: "flex", alignItems: "center", borderBottom: "1px solid #f0f0f0",
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <span style={{ marginLeft: 16, fontSize: 16, fontWeight: 500 }}>
            AI 3D 资产生成平台 · 草稿验证版
          </span>
        </Header>

        {/* 内容区 */}
        <Content style={{ margin: 24, padding: 24, background: token.colorBgContainer, borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
