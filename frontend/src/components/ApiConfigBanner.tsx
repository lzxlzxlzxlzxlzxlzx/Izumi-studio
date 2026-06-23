import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button } from 'antd';
import { fetchLlmConfig } from '@/api/client';

const STATIC_PAGES = import.meta.env.VITE_STATIC_PAGES === '1';

export default function ApiConfigBanner() {
  const navigate = useNavigate();
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const [backendOnline, setBackendOnline] = useState(true);

  useEffect(() => {
    fetchLlmConfig()
      .then((s) => {
        setLlmConfigured(s.llm_configured);
        setBackendOnline(true);
      })
      .catch(() => {
        setBackendOnline(false);
        setLlmConfigured(null);
      });
  }, []);

  if (STATIC_PAGES) {
    return (
      <Alert
        type="info"
        showIcon
        className="rounded-none border-x-0 border-t-0"
        message="GitLab Pages 静态预览"
        description="此为前端界面预览，聊天/创作需本地或服务器部署完整版（前后端）。克隆仓库后运行 start.sh，并在设置中填写你自己的 API Key。"
      />
    );
  }

  if (!backendOnline) {
    return (
      <Alert
        type="warning"
        showIcon
        className="rounded-none border-x-0 border-t-0"
        message="未连接后端"
        description="请确认后端已启动。局域网访问请使用 http://本机IP:5173"
      />
    );
  }

  if (llmConfigured) return null;

  return (
    <Alert
      type="warning"
      showIcon
      className="rounded-none border-x-0 border-t-0"
      message="尚未配置 API Key"
      description={
        <span>
          请在设置中填写你自己的 DeepSeek / 百炼 API Key 后才能使用聊天与创作功能。
          <Button type="link" size="small" onClick={() => navigate('/settings')}>
            前往设置
          </Button>
        </span>
      }
    />
  );
}
