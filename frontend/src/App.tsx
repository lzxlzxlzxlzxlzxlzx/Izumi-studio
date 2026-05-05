import { Routes, Route, Navigate } from 'react-router-dom';
import CardGalleryPage from './pages/CardGalleryPage';
import CardDetailPage from './pages/CardDetailPage';
import ChatPage from './pages/ChatPage';
import ImportPage from './pages/ImportPage';
import SettingsPage from './pages/SettingsPage';
import PresetsPage from './pages/PresetsPage';
import WorldbooksPage from './pages/WorldbooksPage';

function NotFoundPage() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-300">404</h1>
        <p className="text-gray-400 mt-4">页面未找到</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/cards" replace />} />
      <Route path="/cards" element={<CardGalleryPage />} />
      <Route path="/cards/:cardId" element={<CardDetailPage />} />
      <Route path="/chat/:sessionId" element={<ChatPage />} />
      <Route path="/import" element={<ImportPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/presets" element={<PresetsPage />} />
      <Route path="/worldbooks" element={<WorldbooksPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
