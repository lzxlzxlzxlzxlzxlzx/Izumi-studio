import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Switch, Select, Input, Card, Divider, message } from 'antd';
import {
  ArrowLeftOutlined,
  ApiOutlined,
  RobotOutlined,
  SettingOutlined,
  BellOutlined,
} from '@ant-design/icons';

interface Settings {
  model: string;
  temperature: number;
  maxTokens: number;
  wordCountMin: number;
  wordCountMax: number;
  autoSummarize: boolean;
  summarizeInterval: number;
  notifyOnComplete: boolean;
}

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem('izumi-settings');
    if (raw) return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return defaultSettings();
}

function defaultSettings(): Settings {
  return {
    model: 'deepseek-v4-pro',
    temperature: 0.8,
    maxTokens: 2048,
    wordCountMin: 50,
    wordCountMax: 200,
    autoSummarize: true,
    summarizeInterval: 6,
    notifyOnComplete: true,
  };
}

const MODEL_OPTIONS = [
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro (推荐)' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
  { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner' },
  { value: 'qwen-plus', label: 'Qwen Plus (DashScope)' },
  { value: 'qwen-max', label: 'Qwen Max (DashScope)' },
  { value: 'moonshot-v1-8k', label: 'Kimi (Moonshot V1 8k)' },
];

export default function SettingsPage() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [saved, setSaved] = useState(false);

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  function handleSave() {
    localStorage.setItem('izumi-settings', JSON.stringify(settings));
    message.success('设置已保存');
    setSaved(true);
  }

  return (
    <div className="min-h-screen bg-[#f8f4f0]">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-4">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(-1)}
            className="text-gray-400 hover:text-gray-700"
          />
          <h1 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <SettingOutlined />
            设置
          </h1>
          <div className="flex-1" />
          <Button
            type="primary"
            onClick={handleSave}
            className="bg-primary-500 hover:bg-primary-600"
          >
            保存
          </Button>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* 模型设置 */}
        <Card
          className="bg-white border-gray-200"
          title={
            <span className="flex items-center gap-2 text-gray-800">
              <RobotOutlined className="text-primary-400" /> 模型
            </span>
          }
        >
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 block mb-2">默认模型</label>
              <Select
                value={settings.model}
                onChange={(v) => update('model', v)}
                className="w-full"
                options={MODEL_OPTIONS}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400 block mb-2">温度 ({settings.temperature})</label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={settings.temperature}
                  onChange={(e) => update('temperature', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-2">最大Token数</label>
                <Input
                  type="number"
                  value={settings.maxTokens}
                  onChange={(e) => update('maxTokens', parseInt(e.target.value) || 2048)}
                  min={256}
                  max={8192}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400 block mb-2">最低字数</label>
                <Input
                  type="number"
                  value={settings.wordCountMin}
                  onChange={(e) => update('wordCountMin', parseInt(e.target.value) || 50)}
                  min={10}
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-2">最高字数</label>
                <Input
                  type="number"
                  value={settings.wordCountMax}
                  onChange={(e) => update('wordCountMax', parseInt(e.target.value) || 200)}
                  min={50}
                />
              </div>
            </div>
          </div>
        </Card>

        {/* 记忆设置 */}
        <Card
          className="bg-white border-gray-200"
          title={
            <span className="flex items-center gap-2 text-gray-800">
              <ApiOutlined className="text-green-400" /> 记忆
            </span>
          }
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-800">自动摘要</div>
                <div className="text-xs text-gray-400">自动创建对话摘要</div>
              </div>
              <Switch
                checked={settings.autoSummarize}
                onChange={(v) => update('autoSummarize', v)}
              />
            </div>

            {settings.autoSummarize && (
              <div>
                <label className="text-sm text-gray-400 block mb-2">每 N 轮摘要一次</label>
                <Input
                  type="number"
                  value={settings.summarizeInterval}
                  onChange={(e) => update('summarizeInterval', parseInt(e.target.value) || 6)}
                  min={2}
                  max={20}
                  className="w-32"
                />
              </div>
            )}
          </div>
        </Card>

        {/* 通知 */}
        <Card
          className="bg-white border-gray-200"
          title={
            <span className="flex items-center gap-2 text-gray-800">
              <BellOutlined className="text-amber-400" /> 通知
            </span>
          }
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-800">生成完成</div>
              <div className="text-xs text-gray-400">回复完成后显示通知</div>
            </div>
            <Switch
              checked={settings.notifyOnComplete}
              onChange={(v) => update('notifyOnComplete', v)}
            />
          </div>
        </Card>

        <Divider className="border-gray-200" />

        <div className="text-xs text-gray-300 space-y-1">
          <p>Izumi Studio v0.1.0</p>
          <p>设置保存在浏览器本地存储中。</p>
        </div>
      </div>
    </div>
  );
}
