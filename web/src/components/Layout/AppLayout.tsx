import { useState } from "react";
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

const { Header, Sider, Content } = Layout;

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

  return (
    <Layout className="app-layout" style={{ minHeight: "100vh" }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark">
        <div style={{
          height: 64, display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontSize: collapsed ? 14 : 18, fontWeight: 700,
          borderBottom: "1px solid rgba(255,255,255,0.1)",
          whiteSpace: "nowrap", overflow: "hidden",
        }}>
          {collapsed ? "A3D" : "AI 3D 平台"}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
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
        <Content style={{ margin: 24, padding: 24, background: token.colorBgContainer, borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
