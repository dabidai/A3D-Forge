import { useQuery } from "@tanstack/react-query";
import { Row, Col, Card, Statistic, Table, Tag, Spin } from "antd";
import {
  CubeOutlined, CheckCircleOutlined, CloseCircleOutlined, ToolOutlined,
} from "@ant-design/icons";
import { listAssets, listTasks } from "@/api/endpoints";
import type { AssetInfo, TaskInfo } from "@/types";
import dayjs from "dayjs";

export default function Dashboard() {
  const { data: assetsData, isLoading: assetsLoading } = useQuery({
    queryKey: ["assets", { page: 1, page_size: 100 }],
    queryFn: () => listAssets({ page: 1, page_size: 100 }),
    refetchInterval: 15000,
  });
  const { data: tasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => listTasks({ limit: 20 }),
    refetchInterval: 10000,
  });

  const assets: AssetInfo[] = assetsData?.data?.items || [];
  const tasks: TaskInfo[] = tasksData?.data?.items || [];

  const processed = assets.filter((a) => a.status === "processed").length;
  const failed = assets.filter((a) => a.status === "failed").length;
  const generating = assets.filter((a) => ["generating", "processing"].includes(a.status)).length;
  const totalFaces = assets.reduce((sum, a) => sum + (a.face_count || 0), 0);

  const statusColor: Record<string, string> = {
    generated: "blue", generating: "processing", processed: "green",
    failed: "red", pending: "default", running: "blue", success: "green",
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}><Card><Statistic title="总资产数" value={assets.length} prefix={<CubeOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="已处理" value={processed} prefix={<CheckCircleOutlined />} valueStyle={{ color: "#3f8600" }} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="生成中" value={generating} prefix={<ToolOutlined spin={generating > 0} />} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="失败" value={failed} prefix={<CloseCircleOutlined />} valueStyle={{ color: "#cf1322" }} /></Card></Col>
      </Row>

      <Card title="最近资产" style={{ marginTop: 24 }}>
        <Table<AssetInfo>
          dataSource={assets.slice(0, 10)}
          rowKey="id"
          loading={assetsLoading}
          size="small"
          columns={[
            { title: "名称", dataIndex: "name", ellipsis: true },
            { title: "类型", dataIndex: "asset_type", render: (t) => t === "text_to_3d" ? "文生3D" : "图生3D" },
            { title: "状态", dataIndex: "status", render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> },
            { title: "面数", dataIndex: "face_count", render: (v) => v?.toLocaleString() || "-" },
            { title: "创建时间", dataIndex: "created_at", render: (v) => dayjs(v).format("MM-DD HH:mm") },
          ]}
        />
      </Card>

      <Card title="最近任务" style={{ marginTop: 16 }}>
        <Table<TaskInfo>
          dataSource={tasks.slice(0, 10)}
          rowKey="id"
          loading={tasksLoading}
          size="small"
          columns={[
            { title: "类型", dataIndex: "task_type" },
            { title: "状态", dataIndex: "status", render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> },
            { title: "进度", dataIndex: "progress", render: (v: number) => `${Math.round(v * 100)}%` },
            { title: "创建时间", dataIndex: "created_at", render: (v) => dayjs(v).format("MM-DD HH:mm") },
            { title: "错误", dataIndex: "error_message", ellipsis: true, render: (v) => v || "-" },
          ]}
        />
      </Card>
    </div>
  );
}
