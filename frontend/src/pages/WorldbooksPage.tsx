import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Spin, Empty, message, Popconfirm, Drawer, Tag } from 'antd';
import {
  ArrowLeftOutlined,
  DeleteOutlined,
  EyeOutlined,
  BookOutlined,
} from '@ant-design/icons';
import { fetchWorldbooks, getWorldbook, deleteWorldbook } from '@/api/client';

interface WBInfo {
  id: string;
  name: string;
  file_path: string;
  created_at: string;
  updated_at: string;
}

export default function WorldbooksPage() {
  const navigate = useNavigate();
  const [wbs, setWbs] = useState<WBInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => { loadWorldbooks(); }, []);

  async function loadWorldbooks() {
    setLoading(true);
    try {
      const data = await fetchWorldbooks();
      setWbs(data);
    } catch {
      message.error('加载世界书失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleView(id: string) {
    try {
      const data = await getWorldbook(id);
      setDetail(data);
      setDetailOpen(true);
    } catch {
      message.error('加载世界书详情失败');
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteWorldbook(id);
      message.success('世界书已删除');
      loadWorldbooks();
    } catch {
      message.error('删除世界书失败');
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f4f0]">
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-4">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/cards')}
            className="text-gray-400 hover:text-gray-700"
          />
          <h1 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <BookOutlined /> 世界书
          </h1>
          <span className="text-sm text-gray-400">共 {wbs.length} 本</span>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8">
        {loading ? (
          <div className="flex justify-center py-12"><Spin size="large" /></div>
        ) : wbs.length === 0 ? (
          <Empty description="暂无导入的世界书 — 请使用导入页面添加世界书" />
        ) : (
          <div className="flex flex-col gap-3">
            {wbs.map((wb) => (
              <div
                key={wb.id}
                className="bg-white rounded-lg p-4 border border-gray-200 flex items-center gap-4"
              >
                <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center">
                  <BookOutlined className="text-gray-400" />
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-gray-800">{wb.name}</h3>
                  <p className="text-xs text-gray-400 mt-1">
                    更新于: {wb.updated_at || wb.created_at}
                  </p>
                </div>
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={() => handleView(wb.id)}
                  className="text-gray-400 hover:text-gray-700"
                />
                <Popconfirm title="确定删除此世界书？" onConfirm={() => handleDelete(wb.id)}>
                  <Button
                    type="text"
                    icon={<DeleteOutlined />}
                    danger
                    className="text-gray-400 hover:text-red-400"
                  />
                </Popconfirm>
              </div>
            ))}
          </div>
        )}
      </div>

      <Drawer
        title={<span className="text-gray-800">{detail?.name || '世界书'}</span>}
        placement="right"
        width={560}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        styles={{
          header: { background: '#ffffff', borderBottom: '1px solid #e5e7eb' },
          body: { background: '#ffffff', padding: '16px' },
        }}
      >
        {detail && (
          <div className="space-y-4">
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">设置</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="text-gray-400">描述</div>
                <div className="text-gray-600">{detail.description || '—'}</div>
                <div className="text-gray-400">扫描深度</div>
                <div className="text-gray-600">{detail.scan_depth}</div>
                <div className="text-gray-400">Token 预算</div>
                <div className="text-gray-600">{detail.token_budget}</div>
                <div className="text-gray-400">递归扫描</div>
                <div className="text-gray-600">{String(detail.recursive_scanning)}</div>
                <div className="text-gray-400">区分大小写</div>
                <div className="text-gray-600">{String(detail.case_sensitive)}</div>
                <div className="text-gray-400">全词匹配</div>
                <div className="text-gray-600">{String(detail.match_whole_words)}</div>
                <div className="text-gray-400">插入策略</div>
                <div className="text-gray-600">{detail.insertion_strategy}</div>
              </div>
            </section>

            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                条目 ({detail.entries?.length || 0})
              </h3>
              {detail.entries?.length > 0 ? (
                <div className="space-y-2">
                  {detail.entries.map((entry: any, i: number) => (
                    <div key={entry.id || i} className="bg-white rounded p-3 border border-gray-200">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-800 text-sm">{entry.title || `条目 #${i + 1}`}</span>
                        <Tag color={entry.enabled ? 'green' : 'default'} className="text-[10px]">
                          {entry.enabled ? '启用' : '关闭'}
                        </Tag>
                        {entry.constant && <Tag className="text-[10px]">常量</Tag>}
                        <span className="ml-auto text-[10px] text-gray-400">优先级 {entry.priority}</span>
                      </div>
                      {entry.keys?.length > 0 && (
                        <div className="flex flex-wrap gap-1 my-1">
                          {entry.keys.map((k: string) => (
                            <Tag key={k} className="text-[10px]">{k}</Tag>
                          ))}
                        </div>
                      )}
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2 whitespace-pre-wrap">
                        {entry.content?.slice(0, 200)}
                      </p>
                      <div className="flex gap-3 mt-1 text-[10px] text-gray-300">
                        <span>位置: {entry.position}</span>
                        <span>逻辑: {entry.selective_logic}</span>
                        {entry.category && <span>分类: {entry.category}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">此世界书中暂无条目</p>
              )}
            </section>
          </div>
        )}
      </Drawer>
    </div>
  );
}
