/**
 * 模型修复页面。
 *
 * 功能:
 *   1. 加载资产 — 输入资产ID → 查询详情 + 缺陷列表 + 3D预览
 *   2. 自动修复 — 触发 Celery repair_model_task（缺陷检测 → 轻修复 → 导出）
 *   3. LLM分析 — 触发 Qwen3 TECH_ANALYST 深度分析缺陷
 *   4. 缺陷概览卡片 — 总数/严重等级/可修复比例
 *   5. 修复报告 — 展示修复前后对比（面数变化 + 修复类型标签）
 *   6. 缺陷表格 — 可展开查看LLM生成的修复教程，支持下载
 *   7. 模型预览 — 支持原始/修复后模型切换
 */
import { useState } from "react";
import { Card, Input, Button, Table, Tag, Space, message, Collapse, Typography, Row, Col, Statistic, Descriptions } from "antd";
import { ToolOutlined, BugOutlined, RobotOutlined, ReloadOutlined, DownloadOutlined, SwapOutlined } from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import { autoRepair, analyzeDefects, getDefects, getAsset } from "@/api/endpoints";
import { useAppStore } from "@/stores/useAppStore";
import ModelViewer from "@/components/ModelViewer";
import type { DefectInfo, AssetInfo } from "@/types";

const { Paragraph } = Typography;

export default function Repair() {
  const [assetId, setAssetId] = useState("");
  const [activeAssetId, setActiveAssetId] = useState<string | null>(null);
  const [showRepaired, setShowRepaired] = useState(false);  // 模型切换：原始/修复后
  const logAction = useAppStore((s) => s.logAction);

  // 资产详情查询
  const { data: assetData, refetch: refetchAsset } = useQuery({
    queryKey: ["asset", activeAssetId],
    queryFn: () => getAsset(activeAssetId!),
    enabled: !!activeAssetId,
  });

  // 缺陷列表查询
  const { data: defectsData, refetch: refetchDefects } = useQuery({
    queryKey: ["defects", activeAssetId],
    queryFn: () => getDefects(activeAssetId!),
    enabled: !!activeAssetId,
  });

  const asset: AssetInfo | undefined = assetData?.data;
  const defects: DefectInfo[] = defectsData?.data?.defects || [];

  // 自动修复提交
  const repairMutation = useMutation({
    mutationFn: () => autoRepair(activeAssetId!),
    onSuccess: () => {
      logAction("auto_repair", "模型修复", activeAssetId!);
      message.success("修复任务已提交");
      setTimeout(() => { refetchAsset(); refetchDefects(); }, 3000);
    },
    onError: () => message.error("修复失败"),
  });

  // LLM缺陷分析提交
  const analysisMutation = useMutation({
    mutationFn: () => analyzeDefects(activeAssetId!),
    onSuccess: (res) => {
      logAction("llm_analysis", "模型修复", activeAssetId!);
      message.success("LLM 缺陷分析完成");
      refetchDefects();
    },
    onError: () => message.error("分析失败"),
  });

  /** 按资产ID加载 */
  const handleLoad = () => {
    if (!assetId.trim()) { message.warning("请输入资产ID"); return; }
    setActiveAssetId(assetId.trim());
    setShowRepaired(false);
  };

  // 缺陷统计
  const mildCount = defects.filter((d) => d.level === "mild").length;
  const moderateCount = defects.filter((d) => d.level === "moderate").length;
  const severeCount = defects.filter((d) => d.level === "severe").length;
  const repairableCount = defects.filter((d) => d.repairable).length;

  const levelColor: Record<string, string> = { mild: "gold", moderate: "orange", severe: "red" };
  const levelLabel: Record<string, string> = { mild: "轻微", moderate: "中等", severe: "严重" };

  const originalModelUrl = asset?.glb_path
    ? `/static/assets/${activeAssetId}/${activeAssetId}.glb`
    : undefined;
  const repairedModelUrl = originalModelUrl;  // 修复后覆盖原文件，复用同一URL

  const tags = asset?.tags as Record<string, unknown> | undefined;
  const repairReport = tags?.repair_report as Record<string, unknown> | undefined;

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>模型修复</h2>

      {/* 资产ID输入 */}
      <Card>
        <Space>
          <Input placeholder="输入资产 ID" value={assetId} onChange={(e) => setAssetId(e.target.value)}
            onPressEnter={handleLoad} style={{ width: 400 }} />
          <Button type="primary" onClick={handleLoad}>加载资产</Button>
        </Space>
      </Card>

      {activeAssetId && (
        <>
          {/* 缺陷概览卡片 */}
          {defects.length > 0 && (
            <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
              <Col xs={8}><Card size="small"><Statistic title="缺陷总数" value={defects.length} prefix={<BugOutlined />} /></Card></Col>
              <Col xs={8}><Card size="small">
                <Statistic title="严重程度" value={`${severeCount > 0 ? "严重" : moderateCount > 2 ? "中等" : "轻微"}`}
                  valueStyle={{ color: severeCount > 0 ? "#cf1322" : moderateCount > 2 ? "#fa8c16" : "#3f8600" }} />
              </Card></Col>
              <Col xs={8}><Card size="small"><Statistic title="可自动修复" value={`${repairableCount}/${defects.length}`} suffix="项" /></Card></Col>
            </Row>
          )}

          {/* 3D模型预览 — 支持原始/修复后切换 */}
          <Card title={
            <Space>
              <span>3D 预览</span>
              {asset?.processed_model_path && asset?.original_model_path && (
                <Button size="small" icon={<SwapOutlined />}
                  type={showRepaired ? "primary" : "default"}
                  onClick={() => setShowRepaired(!showRepaired)}
                >
                  {showRepaired ? "当前: 修复后" : "当前: 原始"}
                </Button>
              )}
            </Space>
          } style={{ marginTop: 24 }}>
            <ModelViewer modelUrl={showRepaired ? repairedModelUrl : originalModelUrl} />
          </Card>

          {/* 修复操作按钮 */}
          <Card title="修复操作" style={{ marginTop: 24 }}>
            <Space size="large">
              <Button type="primary" icon={<ToolOutlined />} size="large"
                loading={repairMutation.isPending} onClick={() => repairMutation.mutate()}>
                自动检测 + 轻修复
              </Button>
              <Button icon={<RobotOutlined />} size="large"
                loading={analysisMutation.isPending} onClick={() => analysisMutation.mutate()}>
                LLM 深度分析
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => { refetchAsset(); refetchDefects(); }}>
                刷新状态
              </Button>
            </Space>
          </Card>

          {/* 资产信息 */}
          {asset && (
            <Card title="资产信息" size="small" style={{ marginTop: 24 }}>
              <Descriptions column={3} size="small" bordered>
                <Descriptions.Item label="名称">{asset.name}</Descriptions.Item>
                <Descriptions.Item label="类型">{asset.asset_type === "text_to_3d" ? "文生3D" : "图生3D"}</Descriptions.Item>
                <Descriptions.Item label="状态">{asset.status}</Descriptions.Item>
                <Descriptions.Item label="面数">{asset.face_count?.toLocaleString() || "-"}</Descriptions.Item>
                <Descriptions.Item label="顶点数">{asset.vertex_count?.toLocaleString() || "-"}</Descriptions.Item>
                <Descriptions.Item label="API">{asset.api_provider || "-"}</Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {/* 修复报告（面数变化 + 修复步骤标签） */}
          {repairReport && (
            <Card title="修复报告" size="small" style={{ marginTop: 16 }}>
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="原始面数">{String(repairReport.original_faces)}</Descriptions.Item>
                <Descriptions.Item label="修复后面数">{String(repairReport.final_faces)}</Descriptions.Item>
              </Descriptions>
              {Array.isArray(repairReport.repairs) && (
                <div style={{ marginTop: 8 }}>
                  {repairReport.repairs.map((r: Record<string, unknown>, i: number) => (
                    <Tag key={i} color="blue">{String(r.type)}</Tag>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* 缺陷列表 — 可展开查看修复教程 */}
          <Card title={<span><BugOutlined /> 缺陷列表 ({defects.length})</span>} style={{ marginTop: 24 }}>
            <Table<DefectInfo> dataSource={defects} rowKey="id" size="small"
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
                      <>
                        <Paragraph style={{ whiteSpace: "pre-wrap" }}>{record.tutorial}</Paragraph>
                        <Button size="small" icon={<DownloadOutlined />}
                          onClick={() => {
                            const blob = new Blob([record.tutorial || ""], { type: "text/plain" });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `repair_tutorial_${record.type}.txt`;
                            a.click();
                            URL.revokeObjectURL(url);
                          }}
                        >
                          下载修复教程
                        </Button>
                      </>
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
