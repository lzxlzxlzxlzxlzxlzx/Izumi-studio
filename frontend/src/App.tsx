import { Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './components/MainLayout';
import CardGalleryPage from './pages/CardGalleryPage';
import CardDetailPage from './pages/CardDetailPage';
import ChatPage from './pages/ChatPage';
import ImportPage from './pages/ImportPage';
import SettingsPage from './pages/SettingsPage';
import PresetsPage from './pages/PresetsPage';
import WorldbooksPage from './pages/WorldbooksPage';
import ConversationPage from './pages/ConversationPage';
import CreationPage from './pages/CreationPage';

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
      {/* Main pages with bottom navigation */}
      <Route element={<MainLayout />}>
        <Route path="/" element={<Navigate to="/cards" replace />} />
        <Route path="/cards" element={<CardGalleryPage />} />
        <Route path="/cards/:cardId" element={<CardDetailPage />} />
        <Route path="/chat/:sessionId" element={<ChatPage />} />
        <Route path="/konata" element={<ConversationPage />} />
        <Route path="/konata/:sessionId" element={<ConversationPage />} />
        <Route path="/creation" element={<CreationPage />} />
        <Route path="/creation/:sessionId" element={<CreationPage />} />
      </Route>

      {/* Utility pages — no bottom nav */}
      <Route path="/import" element={<ImportPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/presets" element={<PresetsPage />} />
      <Route path="/worldbooks" element={<WorldbooksPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
