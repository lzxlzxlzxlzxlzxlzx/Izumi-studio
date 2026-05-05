import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, Button, Input, Select, Card, message, Space, Tabs } from 'antd';
import {
  ArrowLeftOutlined,
  UploadOutlined,
  FileTextOutlined,
  FileAddOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload';

const { Dragger } = Upload;

type ImportType = 'card' | 'worldbook' | 'preset';

interface ImportResult {
  type: ImportType;
  name: string;
  ok: boolean;
}

export default function ImportPage() {
  const navigate = useNavigate();
  const [importType, setImportType] = useState<ImportType>('card');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ImportResult[]>([]);
  const [extraName, setExtraName] = useState('');
  const [extraDesc, setExtraDesc] = useState('');

  async function handleImport() {
    if (fileList.length === 0) {
      message.warning('请先选择文件');
      return;
    }

    const file = fileList[0].originFileObj;
    if (!file) return;

    setImporting(true);

    const formData = new FormData();
    formData.append('file', file);
    if (extraName) formData.append('name', extraName);
    if (extraDesc && importType === 'worldbook') formData.append('description', extraDesc);

    try {
      const resp = await fetch(`/api/import/${importType}`, {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || '导入失败');
      }

      const data = await resp.json();

      setResults((prev) => [
        ...prev,
        {
          type: importType,
          name: data.card?.name || data.worldbook?.name || data.preset?.name || file.name,
          ok: true,
        },
      ]);

      setFileList([]);
      setExtraName('');
      setExtraDesc('');
      message.success('导入成功');
    } catch (err: any) {
      message.error(err.message || '导入失败');
      setResults((prev) => [
        ...prev,
        { type: importType, name: file.name, ok: false },
      ]);
    } finally {
      setImporting(false);
    }
  }

  const typeLabel: Record<ImportType, string> = {
    card: '角色卡',
    worldbook: '世界书',
    preset: '预设',
  };

  const typeIcon: Record<ImportType, React.ReactNode> = {
    card: <FileAddOutlined />,
    worldbook: <FileTextOutlined />,
    preset: <FileTextOutlined />,
  };

  return (
    <div className="min-h-screen bg-[#f8f4f0]">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-4">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/cards')}
            className="text-gray-400 hover:text-gray-700"
          />
          <h1 className="text-lg font-bold text-gray-800">导入 ST 数据</h1>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Type Selector */}
        <div className="mb-6">
          <label className="text-sm text-gray-400 block mb-2">导入类型</label>
          <Select
            value={importType}
            onChange={(v) => { setImportType(v); setFileList([]); }}
            className="w-48"
            options={[
              { value: 'card', label: '角色卡 (.json / .png)' },
              { value: 'worldbook', label: '世界书 (.json)' },
              { value: 'preset', label: '预设 (.json)' },
            ]}
          />
        </div>

        {/* Optional name/description */}
        {(importType === 'worldbook' || importType === 'preset') && (
          <div className="flex gap-4 mb-6">
            <div className="flex-1">
              <label className="text-sm text-gray-400 block mb-1">自定义名称（可选）</label>
              <Input
                value={extraName}
                onChange={(e) => setExtraName(e.target.value)}
                placeholder="留空则使用文件名"
              />
            </div>
            {importType === 'worldbook' && (
              <div className="flex-1">
                <label className="text-sm text-gray-400 block mb-1">描述（可选）</label>
                <Input
                  value={extraDesc}
                  onChange={(e) => setExtraDesc(e.target.value)}
                  placeholder="简短描述"
                />
              </div>
            )}
          </div>
        )}

        {/* Upload Area */}
        <Card className="bg-white border-gray-200">
          <Dragger
            fileList={fileList}
            beforeUpload={(file) => {
              const ext = file.name.toLowerCase();
              const valid = importType === 'card'
                ? (ext.endsWith('.json') || ext.endsWith('.png'))
                : ext.endsWith('.json');
              if (!valid) {
                message.error(importType === 'card' ? '仅接受 .json 或 .png 文件' : '仅接受 .json 文件');
                return Upload.LIST_IGNORE;
              }
              setFileList([{ uid: '-1', name: file.name, status: 'done', originFileObj: file as any }]);
              return false;
            }}
            onRemove={() => setFileList([])}
            maxCount={1}
            accept={importType === 'card' ? '.json,.png' : '.json'}
            className="bg-white"
          >
            <p className="text-3xl text-gray-400 mb-2">
              <UploadOutlined />
            </p>
            <p className="text-gray-600">点击或拖拽 .json 文件上传</p>
            <p className="text-xs text-gray-400 mt-1">
              SillyTavern V3 {typeLabel[importType]} 格式
            </p>
          </Dragger>
        </Card>

        {/* Import Button */}
        <div className="mt-6 flex justify-end">
          <Button
            type="primary"
            size="large"
            icon={<UploadOutlined />}
            onClick={handleImport}
            loading={importing}
            disabled={fileList.length === 0}
            className="bg-primary-500 hover:bg-primary-600"
          >
            导入{typeLabel[importType]}
          </Button>
        </div>

        {/* Results */}
        {results.length > 0 && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              导入历史
            </h2>
            <div className="flex flex-col gap-2">
              {results.map((r, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-3 px-4 py-2 rounded-lg border text-sm ${
                    r.ok
                      ? 'bg-green-50 border-green-200 text-green-700'
                      : 'bg-red-50 border-red-200 text-red-700'
                  }`}
                >
                  {r.ok ? <CheckCircleOutlined /> : <span className="text-red-400">x</span>}
                  <span className="text-gray-400 w-16">{typeLabel[r.type]}</span>
                  <span className="flex-1">{r.name}</span>
                  <span>{r.ok ? '成功' : '失败'}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
