/**
 * 资产管理页面。
 *
 * 功能:
 *   - 分页展示资产列表（搜索/翻页/刷新）
 *   - 预览缩略图展示
 *   - 操作: 查看详情（跳转修复页）、下载GLB、删除（含确认弹窗）
 *   - 自动记录行为日志（查看/下载/删除）
 *   - 15秒轮询刷新状态
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Table, Tag, Button, Space, Input, message, Popconfirm, Image } from "antd";
import { SearchOutlined, DeleteOutlined, DownloadOutlined, ReloadOutlined, EyeOutlined } from "@ant-design/icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { listAssets, deleteAsset, getDownloadUrl } from "@/api/endpoints";
import { useAppStore } from "@/stores/useAppStore";
import type { AssetInfo } from "@/types";
import dayjs from "dayjs";

export default function Assets() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logAction = useAppStore((s) => s.logAction);

  // 资产列表（15s轮询）
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["assets", { page, page_size: 20 }],
    queryFn: () => listAssets({ page, page_size: 20 }),
    refetchInterval: 15000,
  });

  const assets: AssetInfo[] = data?.data?.items || [];
  const total = data?.data?.total || 0;

  // 资产删除
  const deleteMutation = useMutation({
    mutationFn: deleteAsset,
    onSuccess: () => {
      message.success("资产已删除");
      queryClient.invalidateQueries({ queryKey: ["assets"] });
    },
    onError: () => message.error("删除失败"),
  });

  // 状态 → 颜色映射
  const statusColor: Record<string, string> = {
    generated: "blue", generating: "processing", processing: "processing",
    processed: "green", failed: "red",
  };

  // 前端搜索过滤
  const filtered = search
    ? assets.filter((a) => a.name.toLowerCase().includes(search.toLowerCase()))
    : assets;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h2>资产管理</h2>
        <Space>
          <Input prefix={<SearchOutlined />} placeholder="搜索资产名称" value={search}
            onChange={(e) => setSearch(e.target.value)} allowClear style={{ width: 250 }} />
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
        </Space>
      </div>

      <Table<AssetInfo>
        dataSource={filtered}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page, total, pageSize: 20, onChange: setPage,
          showTotal: (t) => `共 ${t} 项`,
        }}
        columns={[
          {
            title: "预览", dataIndex: "preview_image_path", width: 100,
            render: (path: string | undefined) => path
              ? <Image src={`/static/assets/${path?.split("/").slice(-2).join("/")}`} width={60} height={60}
                  style={{ objectFit: "cover", borderRadius: 4 }} />
              : <div style={{ width: 60, height: 60, background: "#f0f0f0", borderRadius: 4,
                  display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>N/A</div>,
          },
          { title: "名称", dataIndex: "name", ellipsis: true },
          { title: "类型", dataIndex: "asset_type", width: 90,
            render: (t) => t === "text_to_3d" ? "文生3D" : "图生3D" },
          { title: "状态", dataIndex: "status", width: 100,
            render: (s: string) => <Tag color={statusColor[s]}>{s}</Tag> },
          { title: "面数", dataIndex: "face_count", width: 100,
            render: (v: number | undefined) => v?.toLocaleString() || "-" },
          { title: "API", dataIndex: "api_provider", width: 80 },
          { title: "创建时间", dataIndex: "created_at", width: 140,
            render: (v: string) => dayjs(v).format("MM-DD HH:mm") },
          {
            title: "操作", key: "actions", width: 200,
            render: (_, record) => (
              <Space size="small">
                <Button size="small" icon={<EyeOutlined />}
                  onClick={() => { logAction("view_asset", "资产管理", record.id); navigate(`/repair`); }}>
                  查看
                </Button>
                <Button size="small" icon={<DownloadOutlined />} disabled={!record.glb_path}
                  onClick={() => {
                    logAction("download_asset", "资产管理", record.id, { format: "glb" });
                    window.open(getDownloadUrl(record.id, "glb"));
                  }}>
                  GLB
                </Button>
                <Popconfirm title="确认删除此资产？" onConfirm={() => {
                  logAction("delete_asset", "资产管理", record.id);
                  deleteMutation.mutate(record.id);
                }}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
    </div>
  );
}
