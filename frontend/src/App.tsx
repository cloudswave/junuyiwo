import { Routes, Route } from 'react-router-dom'
import { App as AntdApp } from 'antd'
import AppLayout from './components/AppLayout'
import HomePage from './pages/HomePage'
import WordsPage from './pages/WordsPage'
import AddWordsPage from './pages/AddWordsPage'
import ReviewPage from './pages/ReviewPage'
import ArticleHistoryPage from './pages/ArticleHistoryPage'
import StatsPage from './pages/StatsPage'
import CuriosityPage from './pages/CuriosityPage'
import KnowledgePage from './pages/KnowledgePage'
import VoiceManagePage from './pages/VoiceManagePage'
import KnownWordsPage from './pages/KnownWordsPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import SeriesReaderPage from './pages/SeriesReaderPage'

export default function App() {
  return (
    <AntdApp>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/words" element={<WordsPage />} />
          <Route path="/add" element={<AddWordsPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/articles" element={<ArticleHistoryPage />} />
          <Route path="/article/:date" element={<ArticleHistoryPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/curiosity" element={<CuriosityPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/voice" element={<VoiceManagePage />} />
          <Route path="/known" element={<KnownWordsPage />} />
          <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
          <Route path="/series/:seriesId" element={<SeriesReaderPage />} />
        </Route>
      </Routes>
    </AntdApp>
  )
}
