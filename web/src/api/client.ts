/**
 * Axios HTTP客户端配置。
 *
 * 全局设置:
 *   - baseURL: /api/v1（所有请求自动拼接前缀）
 *   - timeout: 30s（单次请求超时）
 *   - 错误拦截: 统一提取后端 detail 字段作为错误消息
 */
import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// 响应拦截器：统一错误处理
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || "请求失败";
    console.error("[API Error]", msg);
    return Promise.reject(err);
  }
);

export default apiClient;
