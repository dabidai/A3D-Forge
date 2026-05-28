/**
 * 3D模型预览组件（Three.js + @react-three/fiber）。
 *
 * 功能:
 *   - 加载GLB模型并居中显示
 *   - 实体/线框渲染模式切换
 *   - 自动旋转开关
 *   - OrbitControls 轨道控制器（旋转/缩放/平移）
 *   - 加载进度提示（useProgress）
 *
 * 依赖:
 *   @react-three/fiber  — React声明式Three.js
 *   @react-three/drei   — 辅助组件（OrbitControls/Grid/Html）
 *   three               — 核心3D库
 */
import { Suspense, useState, useCallback } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, useProgress, Html } from "@react-three/drei";
import { Button, Radio, Space, Spin, Empty, App } from "antd";
import * as THREE from "three";

/** 加载进度指示器（Canvas内部使用） */
function Loader() {
  const { progress } = useProgress();
  return (
    <Html center>
      <Spin tip={`加载中 ${Math.round(progress)}%`} />
    </Html>
  );
}

/** 单个模型网格组件，加载GLB并可选应用线框模式 */
function ModelMesh({ url, wireframe }: { url: string; wireframe: boolean }) {
  const [obj, setObj] = useState<THREE.Group | null>(null);
  const { message } = App.useApp();

  useCallback(() => {
    import("three/examples/jsm/loaders/GLTFLoader.js").then(({ GLTFLoader }) => {
      const gltfLoader = new GLTFLoader();
      gltfLoader.load(
        url,
        (gltf) => {
          const scene = gltf.scene;
          // 应用线框模式：遍历所有子网格设置 wireframe 属性
          scene.traverse((child) => {
            if (child instanceof THREE.Mesh) {
              if (wireframe) {
                (child.material as THREE.MeshStandardMaterial).wireframe = true;
              }
            }
          });
          // 居中模型
          const box = new THREE.Box3().setFromObject(scene);
          const center = box.getCenter(new THREE.Vector3());
          scene.position.set(-center.x, -center.y, -center.z);
          setObj(scene);
        },
        undefined,
        () => message.error("模型加载失败"),
      );
    });
  }, [url, wireframe, message]);

  return obj ? <primitive object={obj} /> : null;
}

interface Props {
  /** GLB模型文件的相对URL（如 /static/assets/{id}/{id}.glb），不传则显示空状态 */
  modelUrl?: string;
  className?: string;
}

export default function ModelViewer({ modelUrl, className }: Props) {
  const [wireframe, setWireframe] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);

  if (!modelUrl) {
    return (
      <div className={`model-viewer-container ${className || ""}`} style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Empty description="暂无模型数据，请先生成3D资产" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <div className={`model-viewer-container ${className || ""}`}>
        <Canvas camera={{ position: [3, 2, 5], fov: 50 }}>
          {/* 双光源: 环境光 + 方向光模拟自然光照 */}
          <ambientLight intensity={0.6} />
          <directionalLight position={[5, 10, 5]} intensity={0.8} />
          <directionalLight position={[-5, 0, -5]} intensity={0.3} />

          <Suspense fallback={<Loader />}>
            <ModelMesh url={modelUrl} wireframe={wireframe} />
            <Grid infiniteGrid args={[10, 10]} />
            <OrbitControls autoRotate={autoRotate} autoRotateSpeed={1} />
          </Suspense>
        </Canvas>
      </div>

      {/* 底部工具栏: 线框模式 + 自动旋转 */}
      <div style={{ position: "absolute", bottom: 12, left: 12 }}>
        <Space>
          <Radio.Group value={wireframe ? "wireframe" : "solid"} size="small"
            onChange={(e) => setWireframe(e.target.value === "wireframe")}
            optionType="button" buttonStyle="solid"
          >
            <Radio.Button value="solid">实体</Radio.Button>
            <Radio.Button value="wireframe">线框</Radio.Button>
          </Radio.Group>
          <Button size="small" type={autoRotate ? "primary" : "default"}
            onClick={() => setAutoRotate(!autoRotate)}
          >
            {autoRotate ? "自动旋转:开" : "自动旋转:关"}
          </Button>
        </Space>
      </div>
    </div>
  );
}
