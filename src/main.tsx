import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import App from "./App";
import HomePage from "./pages/HomePage";
import ArticlePage from "./pages/ArticlePage";
import CategoryPage from "./pages/CategoryPage";
import FinancePage from "./pages/FinancePage";
import FinanceNewsPage from "./pages/FinanceNewsPage";
import WeatherPage from "./pages/WeatherPage";
import SavedPage from "./pages/SavedPage";
import SettingsPage from "./pages/SettingsPage";
import ConsolePage from "./pages/ConsolePage";
import PodcastsPage from "./pages/PodcastsPage";
import SearchPage from "./pages/SearchPage";
import NotFoundPage from "./pages/NotFoundPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<HomePage />} />
          <Route path="article/:id" element={<ArticlePage />} />
          <Route path="category/weather" element={<Navigate to="/weather" replace />} />
          <Route path="category/finance" element={<Navigate to="/finance" replace />} />
          <Route path="category/:slug" element={<CategoryPage />} />
          <Route path="finance" element={<FinancePage />} />
          <Route path="finance/news" element={<FinanceNewsPage />} />
          <Route path="weather" element={<WeatherPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="saved" element={<SavedPage />} />
          <Route path="podcasts" element={<PodcastsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="console" element={<ConsolePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
