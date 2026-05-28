/**
 * 操作日志 / 任务记录页面。
 *
 * 两个Tab:
 *   1. 操作日志 — 前端上报的用户行为日志（listLogs API）
 *      - 展示: 时间、操作类型、页面、资产ID、会话ID
 *      - 15秒轮询刷新
 *   2. 任务记录 — Celery异步任务列表（listTasks API）
 *      - 展示: 任务ID、类型、状态、进度、关联资产、输入参数、错误信息
 *      - 支持按状态筛选
 *      - 10秒轮询刷新
 */
import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Select, Space, Tabs } from "antd";
import { useState } from "react";
import { listTasks, listLogs } from "@/api/endpoints";
import type { TaskInfo } from "@/types";
import dayjs from "dayjs";

/** 用户行为日志条目（listLogs API返回的items元素） */
interface UserLogItem {
  id: string;
  session_id: string;
  action: string;
  page?: string;
  asset_id?: string;
  created_at: string;
}

/** 操作类型 → 中文显示名映射 */
const actionLabels: Record<string, string> = {
  page_view: "页面浏览",
  generate_text_to_3d: "文生3D",
  generate_image_to_3d: "图生3D",
  generate_batch: "批量生成",
  auto_repair: "自动修复",
  llm_analysis: "LLM分析",
  view_asset: "查看资产",
  download_asset: "下载资产",
  delete_asset: "删除资产",
};

export default function Logs() {
  const [taskFilter, setTaskFilter] = useState<string>("");

  // 用户行为日志（15s轮询）
  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["user-logs", { limit: 200 }],
    queryFn: () => listLogs({ limit: 200 }),
    refetchInterval: 15000,
  });

  // 任务记录（10s轮询）
  const { data: tasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks", { limit: 200 }],
    queryFn: () => listTasks({ limit: 200 }),
    refetchInterval: 10000,
  });

  const logs: UserLogItem[] = logsData?.data?.items || [];
  const tasks: TaskInfo[] = tasksData?.data?.items || [];

  const filteredTasks = taskFilter
    ? tasks.filter((t) => t.status === taskFilter || t.task_type === taskFilter)
    : tasks;

  const statusColor: Record<string, string> = {
    pending: "default", running: "blue", success: "green", failed: "red", retrying: "orange",
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>操作日志 / 任务记录</h2>

      <Tabs items={[
        {
          key: "behavior",
          label: "操作日志",
          children: (
            <Table<UserLogItem> dataSource={logs} rowKey="id" loading={logsLoading} size="small"
              pagination={{ pageSize: 50, showTotal: (t) => `共 ${t} 条` }}
              columns={[
                { title: "时间", dataIndex: "created_at", width: 160,
                  render: (v: string) => dayjs(v).format("MM-DD HH:mm:ss") },
                { title: "操作", dataIndex: "action", width: 120,
                  render: (a: string) => <Tag>{actionLabels[a] || a}</Tag> },
                { title: "页面", dataIndex: "page", width: 100 },
                { title: "资产", dataIndex: "asset_id", ellipsis: true, width: 120,
                  render: (v: string | undefined) => v ? v.slice(0, 8) + "..." : "-" },
                { title: "会话", dataIndex: "session_id", ellipsis: true, width: 120,
                  render: (v: string) => v.slice(0, 8) + "..." },
              ]}
            />
          ),
        },
        {
          key: "tasks",
          label: "任务记录",
          children: (
            <>
              <Space style={{ marginBottom: 16 }}>
                <Select placeholder="按状态筛选" allowClear style={{ width: 140 }} onChange={setTaskFilter}
                  options={[
                    { value: "success", label: "成功" },
                    { value: "failed", label: "失败" },
                    { value: "running", label: "运行中" },
                    { value: "pending", label: "等待中" },
                  ]}
                />
              </Space>
              <Table<TaskInfo> dataSource={filteredTasks} rowKey="id" loading={tasksLoading} size="small"
                pagination={{ pageSize: 50, showTotal: (t) => `共 ${t} 条` }}
                columns={[
                  { title: "任务ID", dataIndex: "id", ellipsis: true, width: 100,
                    render: (v) => v?.slice(0, 8) + "..." },
                  { title: "类型", dataIndex: "task_type", width: 120 },
                  { title: "状态", dataIndex: "status", width: 80,
                    render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> },
                  { title: "进度", dataIndex: "progress", width: 80,
                    render: (v: number) => `${Math.round(v * 100)}%` },
                  { title: "关联资产", dataIndex: "asset_id", ellipsis: true, width: 100,
                    render: (v) => v?.slice(0, 8) + "..." || "-" },
                  { title: "输入参数", dataIndex: "input_params", ellipsis: true,
                    render: (v) => v ? JSON.stringify(v).slice(0, 80) : "-" },
                  { title: "错误信息", dataIndex: "error_message", ellipsis: true, width: 150,
                    render: (v) => v || "-" },
                  { title: "创建时间", dataIndex: "created_at", width: 140,
                    render: (v) => dayjs(v).format("MM-DD HH:mm:ss") },
                ]}
              />
            </>
          ),
        },
      ]} />
    </div>
  );
}
