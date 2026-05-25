import { useState, useCallback } from "react";
import { Card, Tabs, Input, Button, Select, Upload, message, Space, Progress, Alert } from "antd";
import { InboxOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import { textTo3D, imageTo3D, getGenerationStatus } from "@/api/endpoints";
import ModelViewer from "@/components/ModelViewer";
import type { GenerationStatus } from "@/types";

const { TextArea } = Input;

export default function Generate() {
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [style, setStyle] = useState("realistic");
  const [currentAssetId, setCurrentAssetId] = useState<string | null>(null);
  const [taskMessage, setTaskMessage] = useState("");

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

  const textMutation = useMutation({
    mutationFn: () => textTo3D({ prompt, negative_prompt: negativePrompt, style }),
    onSuccess: (res) => {
      setCurrentAssetId(res.data.asset_id);
      setTaskMessage(res.data.message);
      message.success("文生3D任务已提交");
    },
    onError: () => message.error("提交失败"),
  });

  const imageMutation = useMutation({
    mutationFn: (file: File) => imageTo3D(file, style),
    onSuccess: (res) => {
      setCurrentAssetId(res.data.asset_id);
      setTaskMessage(res.data.message);
      message.success("图生3D任务已提交");
    },
    onError: () => message.error("提交失败"),
  });

  const statusPercent = status ? Math.round(status.progress * 100) : 0;
  const isProcessing = status && ["generating", "processing", "pending"].includes(status.status);

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>3D 生成</h2>
      <Tabs
        items={[
          {
            key: "text",
            label: <span><ThunderboltOutlined /> 文生3D</span>,
            children: (
              <Card>
                <Space direction="vertical" style={{ width: "100%" }} size="middle">
                  <div>
                    <div style={{ marginBottom: 8 }}>正向提示词 (Prompt)</div>
                    <TextArea
                      rows={4}
                      placeholder="描述你想要的3D模型，例如：一把中世纪风格的长剑，带有宝石镶嵌的剑柄，高度细节化"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                    />
                  </div>
                  <div>
                    <div style={{ marginBottom: 8 }}>负向提示词 (Negative Prompt)</div>
                    <TextArea
                      rows={2}
                      placeholder="不想出现的内容，例如：低质量、模糊、变形"
                      value={negativePrompt}
                      onChange={(e) => setNegativePrompt(e.target.value)}
                    />
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
                  <Button type="primary" size="large" icon={<ThunderboltOutlined />}
                    loading={textMutation.isPending}
                    onClick={() => textMutation.mutate()}
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
                <Upload.Dragger
                  accept="image/*"
                  maxCount={1}
                  beforeUpload={(file) => {
                    imageMutation.mutate(file);
                    return false;
                  }}
                  disabled={imageMutation.isPending}
                >
                  <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p>点击或拖拽图片到此区域上传</p>
                  <p style={{ color: "#999" }}>支持 JPG/PNG，建议清晰正面照</p>
                </Upload.Dragger>
              </Card>
            ),
          },
        ]}
      />

      {status && (
        <Card title="生成状态" style={{ marginTop: 24 }}>
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Progress percent={statusPercent} status={status.status === "failed" ? "exception" : isProcessing ? "active" : "success"} />
            <div>状态: {status.status}</div>
            {status.error_message && <Alert type="error" message={status.error_message} />}
          </Space>
        </Card>
      )}

      <Card title="3D 预览" style={{ marginTop: 24 }}>
        <ModelViewer modelUrl={status?.model_url} />
      </Card>

      {status?.face_count && (
        <Card size="small" style={{ marginTop: 16 }}>
          <Space>
            <span>面数: {status.face_count.toLocaleString()}</span>
            <span>状态: {status.status}</span>
          </Space>
        </Card>
      )}
    </div>
  );
}
