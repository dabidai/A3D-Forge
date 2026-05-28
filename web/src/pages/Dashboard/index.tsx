/**
 * 仪表盘页面。
 *
 * 展示内容:
 *   1. 核心统计卡片 — 总资产/已处理/生成中/失败
 *   2. 运营指标 — 生成成功率(7天)/自动修复率/平均缺陷数/总缺陷
 *   3. Top缺陷类型分布 — 进度条可视化
 *   4. 数据导出按钮 — 缺陷数据集CSV / 修复脚本Python
 *   5. 最近资产列表 — 前10条
 *   6. 最近任务列表 — 前10条
 *
 * 数据刷新:
 *   - 资产列表: 15秒轮询
 *   - 任务列表: 10秒轮询
 *   - 统计数据: 30秒轮询
 */
import { useQuery } from "@tanstack/react-query";
import { Row, Col, Card, Statistic, Table, Tag, Spin, Progress, Button, Space } from "antd";
import {
  CubeOutlined, CheckCircleOutlined, CloseCircleOutlined, ToolOutlined,
  BugOutlined, ThunderboltOutlined, BarChartOutlined, DownloadOutlined,
} from "@ant-design/icons";
import { listAssets, listTasks, getStatsOverview } from "@/api/endpoints";
import type { AssetInfo, TaskInfo, StatsOverview } from "@/types";
import dayjs from "dayjs";

export default function Dashboard() {
  // 资产数据（15s轮询）
  const { data: assetsData, isLoading: assetsLoading } = useQuery({
    queryKey: ["assets", { page: 1, page_size: 100 }],
    queryFn: () => listAssets({ page: 1, page_size: 100 }),
    refetchInterval: 15000,
  });
  // 任务数据（10s轮询）
  const { data: tasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => listTasks({ limit: 20 }),
    refetchInterval: 10000,
  });
  // 统计数据（30s轮询）
  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ["stats-overview"],
    queryFn: getStatsOverview,
    refetchInterval: 30000,
  });

  const assets: AssetInfo[] = assetsData?.data?.items || [];
  const tasks: TaskInfo[] = tasksData?.data?.items || [];
  const stats: StatsOverview | undefined = statsData?.data;

  // 各状态资产计数
  const processed = assets.filter((a) => a.status === "processed").length;
  const failed = assets.filter((a) => a.status === "failed").length;
  const generating = assets.filter((a) => ["generating", "processing"].includes(a.status)).length;

  // 状态 → 颜色映射
  const statusColor: Record<string, string> = {
    generated: "blue", generating: "processing", processed: "green",
    failed: "red", pending: "default", running: "blue", success: "green",
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>

      {/* 第一行: 核心统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}><Card><Statistic title="总资产数" value={assets.length} prefix={<CubeOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="已处理" value={processed} prefix={<CheckCircleOutlined />} valueStyle={{ color: "#3f8600" }} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="生成中" value={generating} prefix={<ToolOutlined spin={generating > 0} />} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="失败" value={failed} prefix={<CloseCircleOutlined />} valueStyle={{ color: "#cf1322" }} /></Card></Col>
      </Row>

      {/* 第二行: 运营指标（来自 stats API） */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="生成成功率(7天)" value={stats.generation_success_rate} suffix="%" prefix={<ThunderboltOutlined />}
                valueStyle={{ color: stats.generation_success_rate > 50 ? "#3f8600" : "#cf1322" }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="自动修复率(7天)" value={stats.auto_repair_rate} suffix="%" prefix={<ToolOutlined />}
                valueStyle={{ color: stats.auto_repair_rate > 50 ? "#3f8600" : "#cf1322" }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="平均缺陷数/模型" value={stats.avg_defects_per_model} prefix={<BugOutlined />} precision={1} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="总缺陷记录" value={stats.total_defects} prefix={<BarChartOutlined />} />
            </Card>
          </Col>
        </Row>
      )}

      {/* 缺陷类型Top5（进度条可视化） */}
      {stats && stats.top_defect_types && stats.top_defect_types.length > 0 && (
        <Card title="Top 缺陷类型" size="small" style={{ marginTop: 16 }}>
          {stats.top_defect_types.map((d, i) => (
            <div key={d.type} style={{ display: "flex", alignItems: "center", marginBottom: 8, gap: 12 }}>
              <Tag>{d.type}</Tag>
              <Progress percent={Math.round(d.count / stats.total_defects * 100)} size="small"
                style={{ flex: 1 }} format={() => `${d.count} 次`} />
            </div>
          ))}
        </Card>
      )}

      {/* 数据导出按钮 */}
      <Card title="数据导出" size="small" style={{ marginTop: 16 }}>
        <Space>
          <Button icon={<DownloadOutlined />} href="/api/v1/export/defects-dataset?format=csv" target="_blank">
            下载缺陷数据集 (CSV)
          </Button>
          <Button icon={<DownloadOutlined />} href="/api/v1/export/repair-scripts/download" target="_blank">
            下载修复脚本库 (Python)
          </Button>
        </Space>
      </Card>

      {/* 最近资产列表（前10条） */}
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

      {/* 最近任务列表（前10条） */}
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
