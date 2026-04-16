import { Routes, Route, Navigate } from "react-router-dom";
import ThemeProvider from "./ThemeProvider";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import SearchPage from "./pages/SearchPage";
import SettingsPage from "./pages/SettingsPage";
import PodcastsPage from "./pages/PodcastsPage";
import NotebookDetailPage from "./pages/NotebookDetailPage";
import SourceDetailPage from "./pages/SourceDetailPage";

export default function App() {
  return (
    <>
      <ThemeProvider />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/podcasts" element={<PodcastsPage />} />
        <Route path="/notebooks/:id" element={<NotebookDetailPage />} />
        <Route path="/sources/:id" element={<SourceDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
