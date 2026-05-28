/**
 * 3D生成页面。
 *
 * 三个Tab:
 *   1. 文生3D      — 输入提示词 → LLM优化 → 内容审核 → 提交Celery任务 → 轮询状态 → 3D预览
 *   2. 图生3D      — 上传图片 → 提交生成任务 → 轮询 → 预览
 *   3. 批量生成    — 多行提示词 → 批量提交 → 表格展示各任务状态
 *
 * LLM优化展示:
 *   当 skipOptimization=false 时，展示原始/优化后提示词对比 + 审核结果
 *
 * 轮询逻辑:
 *   status 为 generating/processing/pending 时每3秒查询一次，完成/失败时停止
 */
import { useState, useCallback } from "react";
import { Card, Tabs, Input, Button, Select, Upload, message, Space, Progress, Alert, Table, Tag, Descriptions, Switch } from "antd";
import { InboxOutlined, ThunderboltOutlined, BarsOutlined } from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import { textTo3D, imageTo3D, batchTextTo3D, getGenerationStatus } from "@/api/endpoints";
import { useAppStore } from "@/stores/useAppStore";
import ModelViewer from "@/components/ModelViewer";
import type { GenerationStatus, TextTo3DResult } from "@/types";

const { TextArea } = Input;

export default function Generate() {
  // 表单状态
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [style, setStyle] = useState("realistic");
  const [skipOptimization, setSkipOptimization] = useState(false);
  const [currentAssetId, setCurrentAssetId] = useState<string | null>(null);
  const [taskMessage, setTaskMessage] = useState("");
  const [llmResult, setLlmResult] = useState<TextTo3DResult | null>(null);
  const logAction = useAppStore((s) => s.logAction);

  // 批量生成状态
  const [batchPrompts, setBatchPrompts] = useState("");
  const [batchResults, setBatchResults] = useState<TextTo3DResult[]>([]);

  // 轮询生成状态
  const { data: statusData } = useQuery({
    queryKey: ["generation-status", currentAssetId],
    queryFn: () => getGenerationStatus(currentAssetId!),
    enabled: !!currentAssetId,
    refetchInterval: (query) => {
      const data = query.state.data?.data as GenerationStatus | undefined;
      if (!data) return 3000;
      return ["generating", "processing", "pending"].includes(data.status) ? 3000 : false;
    },
  });

  const status: GenerationStatus | undefined = statusData?.data;
  const statusPercent = status ? Math.round(status.progress * 100) : 0;
  const isProcessing = status && ["generating", "processing", "pending"].includes(status.status);

  // ---- Mutations ----

  /** 文生3D提交 */
  const textMutation = useMutation({
    mutationFn: () => textTo3D({ prompt, negative_prompt: negativePrompt, style, skip_optimization: skipOptimization }),
    onSuccess: (res) => {
      const result = res.data as TextTo3DResult;
      setLlmResult(result);
      setCurrentAssetId(result.asset_id);
      setTaskMessage(result.message);
      logAction("generate_text_to_3d", "3D生成", result.asset_id, { prompt, style, optimized: !!result.optimized_prompt });
      message.success("文生3D任务已提交");
    },
    onError: () => message.error("提交失败"),
  });

  /** 图生3D提交 */
  const imageMutation = useMutation({
    mutationFn: (file: File) => imageTo3D(file, style),
    onSuccess: (res) => {
      setCurrentAssetId(res.data.asset_id);
      setTaskMessage(res.data.message);
      logAction("generate_image_to_3d", "3D生成", res.data.asset_id, { filename: file.name, style });
      message.success("图生3D任务已提交");
    },
    onError: () => message.error("提交失败"),
  });

  /** 批量文生3D提交 */
  const batchMutation = useMutation({
    mutationFn: () => {
      const prompts = batchPrompts.split("\n").map((s) => s.trim()).filter(Boolean);
      return batchTextTo3D({ prompts, negative_prompt: negativePrompt, style, skip_optimization: skipOptimization });
    },
    onSuccess: (res) => {
      const results = res.data.tasks as TextTo3DResult[];
      setBatchResults(results);
      if (results.length > 0) setCurrentAssetId(results[0].asset_id);
      logAction("generate_batch", "3D生成", undefined, { count: results.length, style });
      message.success(`批量任务已提交: ${results.length} 个`);
    },
    onError: () => message.error("批量提交失败"),
  });

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>3D 生成</h2>

      <Tabs items={[
        {
          key: "text",
          label: <span><ThunderboltOutlined /> 文生3D</span>,
          children: (
            <Card>
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <div>
                  <div style={{ marginBottom: 8 }}>正向提示词 (Prompt)</div>
                  <TextArea rows={4} placeholder="描述你想要的3D模型，例如：一把中世纪风格的长剑，带有宝石镶嵌的剑柄，高度细节化"
                    value={prompt} onChange={(e) => setPrompt(e.target.value)} />
                </div>
                <div>
                  <div style={{ marginBottom: 8 }}>负向提示词 (Negative Prompt)</div>
                  <TextArea rows={2} placeholder="不想出现的内容，例如：低质量、模糊、变形"
                    value={negativePrompt} onChange={(e) => setNegativePrompt(e.target.value)} />
                </div>
                <div>
                  <div style={{ marginBottom: 8 }}>风格</div>
                  <Select value={style} onChange={setStyle} style={{ width: 200 }}
                    options={[
                      { value: "realistic", label: "写实" },
                      { value: "cartoon", label: "卡通" },
                      { value: "low_poly", label: "低多边形" },
                      { value: "sculpture", label: "雕塑" },
                    ]}
                  />
                </div>
                {/* LLM优化开关 */}
                <Space>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span>LLM 优化提示词</span>
                    <Switch checked={!skipOptimization} onChange={(v) => setSkipOptimization(!v)} />
                  </div>
                </Space>
                <Button type="primary" size="large" icon={<ThunderboltOutlined />}
                  loading={textMutation.isPending} onClick={() => textMutation.mutate()}
                  disabled={!prompt.trim()}
                >
                  生成 3D 草稿
                </Button>
              </Space>
            </Card>
          ),
        },
        {
          key: "image",
          label: <span><InboxOutlined /> 图生3D</span>,
          children: (
            <Card>
              <Upload.Dragger accept="image/*" maxCount={1}
                beforeUpload={(file) => { imageMutation.mutate(file); return false; }}
                disabled={imageMutation.isPending}
              >
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p>点击或拖拽图片到此区域上传</p>
                <p style={{ color: "#999" }}>支持 JPG/PNG，建议清晰正面照</p>
              </Upload.Dragger>
            </Card>
          ),
        },
        {
          key: "batch",
          label: <span><BarsOutlined /> 批量生成</span>,
          children: (
            <Card>
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <div>
                  <div style={{ marginBottom: 8 }}>输入多个提示词（每行一个）</div>
                  <TextArea rows={6} placeholder={"一把中世纪长剑\n一面龙纹盾牌\n一个魔法药水瓶\n..."}
                    value={batchPrompts} onChange={(e) => setBatchPrompts(e.target.value)} />
                </div>
                <Button type="primary" size="large" icon={<BarsOutlined />}
                  loading={batchMutation.isPending} onClick={() => batchMutation.mutate()}
                  disabled={!batchPrompts.trim()}
                >
                  批量生成
                </Button>
                {/* 批量任务结果表格 */}
                {batchResults.length > 0 && (
                  <Table<TextTo3DResult> dataSource={batchResults} rowKey="task_id" size="small" pagination={false}
                    columns={[
                      { title: "提示词", dataIndex: "original_prompt", ellipsis: true,
                        render: (v: string | undefined, r) => v || r.message },
                      { title: "状态", dataIndex: "status", width: 80,
                        render: (s: string) => <Tag color={s === "pending" ? "blue" : "green"}>{s}</Tag> },
                      { title: "任务ID", dataIndex: "task_id", width: 100,
                        render: (v: string) => v.slice(0, 8) + "..." },
                    ]}
                  />
                )}
              </Space>
            </Card>
          ),
        },
      ]} />

      {/* LLM优化结果展示：原始/优化后提示词对比 + 审核结果 */}
      {llmResult && (llmResult.optimized_prompt || llmResult.audit_result) && (
        <Card title="LLM 分析结果" size="small" style={{ marginTop: 16 }}>
          {llmResult.optimized_prompt && (
            <Descriptions column={1} size="small" bordered style={{ marginBottom: 12 }}>
              <Descriptions.Item label="原始提示词">{llmResult.original_prompt}</Descriptions.Item>
              <Descriptions.Item label="优化后提示词">
                <span style={{ color: "#1677ff" }}>{llmResult.optimized_prompt}</span>
              </Descriptions.Item>
              {llmResult.optimized_negative_prompt && (
                <Descriptions.Item label="优化后负向提示词">
                  <span style={{ color: "#ff4d4f" }}>{llmResult.optimized_negative_prompt}</span>
                </Descriptions.Item>
              )}
            </Descriptions>
          )}
          {llmResult.audit_result && (
            <Alert
              type={llmResult.audit_result.compliant !== false ? "success" : "warning"}
              message={llmResult.audit_result.compliant !== false ? "内容审核通过" : "内容审核标记"}
              description={JSON.stringify(llmResult.audit_result)}
              style={{ marginTop: 8 }}
            />
          )}
        </Card>
      )}

      {/* 生成状态栏：进度条 + 状态文本 */}
      {status && (
        <Card title="生成状态" style={{ marginTop: 24 }}>
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Progress percent={statusPercent}
              status={status.status === "failed" ? "exception" : isProcessing ? "active" : "success"} />
            <div>状态: {status.status}</div>
            {status.error_message && <Alert type="error" message={status.error_message} />}
          </Space>
        </Card>
      )}

      {/* 3D模型预览器 */}
      <Card title="3D 预览" style={{ marginTop: 24 }}>
        <ModelViewer modelUrl={status?.model_url} />
      </Card>

      {status?.face_count && (
        <Card size="small" style={{ marginTop: 16 }}>
          <Space><span>面数: {status.face_count.toLocaleString()}</span><span>状态: {status.status}</span></Space>
        </Card>
      )}
    </div>
  );
}
