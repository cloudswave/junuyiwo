import { create } from 'zustand'
import type { ArticleResponse, ArticleWithPinyin, ForgottenResponse } from '../services/api'

export interface WordRecord {
  character: string
  pinyin: string | null
  first_date: string
  last_date: string
  count: number
  forget_count: number
  level: string
  tier?: number
}

interface AppState {
  todayCharacters: string[]
  todayMathCharacters: string[]
  todayArticle: ArticleWithPinyin | null
  forgottenStats: Record<string, number>
  totalLearned: number
  totalMathLearned: number

  forgottenItems: ForgottenResponse[]
  forgottenTotal: number

  allCharacters: WordRecord[]

  articles: ArticleResponse[]

  stats: {
    total_characters_learned: number
    total_days: number
    daily_progress: Array<{ date: string; count: number; total: number }>
    forgotten_stats: Record<string, number>
    total_forgotten: number
    total_articles: number
  } | null

  voiceProfileId: number | null

  loading: Record<string, boolean>

  setTodayData: (characters: string[], article: ArticleWithPinyin | null, forgottenStats: Record<string, number>, totalLearned: number, mathCharacters?: string[], totalMathLearned?: number) => void
  setForgotten: (items: ForgottenResponse[], total: number) => void
  setAllCharacters: (chars: WordRecord[]) => void
  setArticles: (articles: ArticleResponse[]) => void
  setStats: (stats: AppState['stats']) => void
  setVoiceProfileId: (id: number | null) => void
  setLoading: (key: string, value: boolean) => void
}

export const useStore = create<AppState>((set) => ({
  todayCharacters: [],
  todayMathCharacters: [],
  todayArticle: null,
  forgottenStats: {},
  totalLearned: 0,
  totalMathLearned: 0,
  forgottenItems: [],
  forgottenTotal: 0,
  allCharacters: [],
  articles: [],
  stats: null,
  voiceProfileId: null,
  loading: {},

  setTodayData: (characters, article, forgottenStats, totalLearned, mathCharacters = [], totalMathLearned = 0) =>
    set({ todayCharacters: characters, todayMathCharacters: mathCharacters, todayArticle: article, forgottenStats, totalLearned, totalMathLearned }),

  setForgotten: (items, total) => set({ forgottenItems: items, forgottenTotal: total }),

  setAllCharacters: (chars) => set({ allCharacters: chars }),

  setArticles: (articles) => set({ articles }),

  setStats: (stats) => set({ stats }),

  setVoiceProfileId: (id) => set({ voiceProfileId: id }),

  setLoading: (key, value) =>
    set((state) => ({ loading: { ...state.loading, [key]: value } })),
}))
