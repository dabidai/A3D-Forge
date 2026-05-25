import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Select, Space } from "antd";
import { useState } from "react";
import { listAssets, listTasks } from "@/api/endpoints";
import type { TaskInfo } from "@/types";
import dayjs from "dayjs";

export default function Logs() {
  const [filter, setFilter] = useState<string>("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["tasks", { limit: 200 }],
    queryFn: () => listTasks({ limit: 200 }),
    refetchInterval: 10000,
  });

  const tasks: TaskInfo[] = data?.data?.items || [];

  const filtered = filter ? tasks.filter((t) => t.status === filter || t.task_type === filter) : tasks;

  const statusColor: Record<string, string> = {
    pending: "default", running: "blue", success: "green", failed: "red", retrying: "orange",
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h2>操作日志 / 任务记录</h2>
        <Space>
          <Select placeholder="按状态筛选" allowClear style={{ width: 140 }} onChange={setFilter}
            options={[
              { value: "success", label: "成功" },
              { value: "failed", label: "失败" },
              { value: "running", label: "运行中" },
              { value: "pending", label: "等待中" },
            ]}
          />
        </Space>
      </div>

      <Table<TaskInfo>
        dataSource={filtered}
        rowKey="id"
        loading={isLoading}
        size="middle"
        columns={[
          { title: "任务ID", dataIndex: "id", ellipsis: true, width: 120, render: (v) => v?.slice(0, 8) + "..." },
          { title: "类型", dataIndex: "task_type", width: 120 },
          { title: "状态", dataIndex: "status", width: 90,
            render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag>,
          },
          { title: "进度", dataIndex: "progress", width: 80,
            render: (v: number) => `${Math.round(v * 100)}%`,
          },
          { title: "关联资产", dataIndex: "asset_id", ellipsis: true, width: 120,
            render: (v) => v?.slice(0, 8) + "..." || "-",
          },
          { title: "输入参数", dataIndex: "input_params", ellipsis: true,
            render: (v) => v ? JSON.stringify(v).slice(0, 80) : "-",
          },
          { title: "错误信息", dataIndex: "error_message", ellipsis: true, width: 150,
            render: (v) => v || "-",
          },
          { title: "创建时间", dataIndex: "created_at", width: 140,
            render: (v) => dayjs(v).format("MM-DD HH:mm:ss"),
          },
        ]}
      />
    </div>
  );
}
