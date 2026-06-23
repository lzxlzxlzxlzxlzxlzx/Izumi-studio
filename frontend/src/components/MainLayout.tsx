import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { PlayCircleOutlined, MessageOutlined, EditOutlined } from '@ant-design/icons';
import ApiConfigBanner from './ApiConfigBanner';

const NAV_ITEMS = [
  {
    path: '/cards',
    label: '游玩',
    icon: <PlayCircleOutlined />,
  },
  {
    path: '/konata',
    label: '对话',
    icon: <MessageOutlined />,
  },
  {
    path: '/creation',
    label: '创作',
    icon: <EditOutlined />,
  },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  // Determine active tab from path prefix
  const activePath = NAV_ITEMS.find((item) =>
    location.pathname.startsWith(item.path)
  )?.path || '/cards';

  return (
    <div className="h-screen flex flex-col bg-[#f8f4f0]">
      <ApiConfigBanner />
      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>

      {/* Bottom Navigation */}
      <nav className="flex-shrink-0 flex items-center justify-center gap-0 bg-white border-t border-gray-200">
        {NAV_ITEMS.map((item) => {
          const isActive = item.path === activePath;
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`flex items-center gap-1.5 px-6 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                isActive
                  ? 'text-purple-600 border-purple-500'
                  : 'text-gray-400 border-transparent hover:text-gray-600'
              }`}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
