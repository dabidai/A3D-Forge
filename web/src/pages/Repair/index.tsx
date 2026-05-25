import { useState } from "react";
import { Card, Input, Button, Table, Tag, Space, message, Collapse, Typography } from "antd";
import { ToolOutlined, BugOutlined, RobotOutlined } from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import { autoRepair, analyzeDefects, getDefects, getAsset } from "@/api/endpoints";
import ModelViewer from "@/components/ModelViewer";
import type { DefectInfo, AssetInfo } from "@/types";

const { Panel } = Collapse;
const { Paragraph } = Typography;

export default function Repair() {
  const [assetId, setAssetId] = useState("");
  const [activeAssetId, setActiveAssetId] = useState<string | null>(null);

  const { data: assetData, refetch: refetchAsset } = useQuery({
    queryKey: ["asset", activeAssetId],
    queryFn: () => getAsset(activeAssetId!),
    enabled: !!activeAssetId,
  });

  const { data: defectsData, refetch: refetchDefects } = useQuery({
    queryKey: ["defects", activeAssetId],
    queryFn: () => getDefects(activeAssetId!),
    enabled: !!activeAssetId,
  });

  const asset: AssetInfo | undefined = assetData?.data;
  const defects: DefectInfo[] = defectsData?.data?.defects || [];

  const repairMutation = useMutation({
    mutationFn: () => autoRepair(activeAssetId!),
    onSuccess: () => {
      message.success("修复任务已提交");
      setTimeout(() => { refetchAsset(); refetchDefects(); }, 3000);
    },
    onError: () => message.error("修复失败"),
  });

  const analysisMutation = useMutation({
    mutationFn: () => analyzeDefects(activeAssetId!),
    onSuccess: (res) => {
      message.success("LLM 缺陷分析完成");
      refetchDefects();
    },
    onError: () => message.error("分析失败"),
  });

  const handleLoad = () => {
    if (!assetId.trim()) { message.warning("请输入资产ID"); return; }
    setActiveAssetId(assetId.trim());
  };

  const levelColor: Record<string, string> = { mild: "gold", moderate: "orange", severe: "red" };
  const levelLabel: Record<string, string> = { mild: "轻微", moderate: "中等", severe: "严重" };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>模型修复</h2>

      <Card>
        <Space>
          <Input placeholder="输入资产 ID" value={assetId} onChange={(e) => setAssetId(e.target.value)}
            onPressEnter={handleLoad} style={{ width: 400 }}
          />
          <Button type="primary" onClick={handleLoad}>加载资产</Button>
        </Space>
      </Card>

      {activeAssetId && (
        <>
          <Card title="3D 预览" style={{ marginTop: 24 }}>
            <ModelViewer
              modelUrl={asset?.glb_path ? `/static/assets/${activeAssetId}/${activeAssetId}.glb` : undefined}
            />
          </Card>

          <Card title="修复操作" style={{ marginTop: 24 }}>
            <Space size="large">
              <Button type="primary" icon={<ToolOutlined />} size="large"
                loading={repairMutation.isPending}
                onClick={() => repairMutation.mutate()}
              >
                自动检测 + 轻修复
              </Button>
              <Button icon={<RobotOutlined />} size="large"
                loading={analysisMutation.isPending}
                onClick={() => analysisMutation.mutate()}
              >
                LLM 深度分析
              </Button>
            </Space>
          </Card>

          <Card title={<span><BugOutlined /> 缺陷列表 ({defects.length})</span>} style={{ marginTop: 24 }}>
            <Table<DefectInfo>
              dataSource={defects}
              rowKey="id"
              size="small"
              columns={[
                { title: "类型", dataIndex: "type" },
                { title: "等级", dataIndex: "level", render: (l: string) => <Tag color={levelColor[l]}>{levelLabel[l] || l}</Tag> },
                { title: "描述", dataIndex: "description", ellipsis: true },
                { title: "可自动修复", dataIndex: "repairable", render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag color="red">否</Tag> },
                { title: "已修复", dataIndex: "repaired", render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag> },
              ]}
              expandable={{
                expandedRowRender: (record) => (
                  <div style={{ padding: 12 }}>
                    {record.tutorial && (
                      <Collapse ghost items={[{
                        key: "tutorial", label: "修复教程",
                        children: <Paragraph style={{ whiteSpace: "pre-wrap" }}>{record.tutorial}</Paragraph>,
                      }]}
                      />
                    )}
                  </div>
                ),
              }}
            />
          </Card>
        </>
      )}
    </div>
  );
}
