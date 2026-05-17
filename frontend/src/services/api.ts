import axios from 'axios'

// 开发模式用 Vite proxy (/api -> 127.0.0.1:8000)，生产模式(APK)用局域网 IP
// 每个位置在 frontend/.env 中配置 VITE_API_HOST（不提交到 git）
const API_HOST = import.meta.env.VITE_API_HOST || 'http://192.168.1.4:8000'
const baseURL = import.meta.env.DEV ? '/api' : `${API_HOST}/api`

const api = axios.create({
  baseURL,
  timeout: 60000,
})

// 自动注入当前学生ID
api.interceptors.request.use((config) => {
  const sid = localStorage.getItem('currentStudentId') || '1'
  config.headers['X-Student-ID'] = sid
  return config
})

// ===== Characters =====
export interface CharacterResponse {
  id: number
  record_date: string
  character: string
  pinyin: string | null
  category: string
}

export interface CharacterListResponse {
  date: string
  characters: CharacterResponse[]
}

export interface RecentCharInfo {
  d: number       // days ago
  t: number       // zone: 0=Scout(系统发现), 1=Target(教学区), 2=Ally(友军区), 3=Lost(战损区)
}

export const charactersApi = {
  create: (data: { record_date: string; characters: string[]; pinyin?: string[]; category?: string }) =>
    api.post<CharacterResponse[]>('/characters/', data),

  list: () => api.get<CharacterListResponse[]>('/characters/'),

  getByDate: (date: string) => api.get<CharacterListResponse>(`/characters/${date}`),

  getAll: (category?: string) => api.get<Array<{ character: string; pinyin: string | null; first_date: string; last_date: string; count: number; category: string }>>('/characters/all', { params: category ? { category } : {} }),

  getRecentDates: (days?: number) => api.get<Record<string, RecentCharInfo>>('/recent-chars', { params: days ? { days } : {} }),

  markKnown: (data: { date: string; character: string; article_id?: number }) =>
    api.post<{ character: string; tier: number; confirm_count: number; promoted: boolean; message: string }>('/characters/mark-known', data),

  extract: (text: string) => api.post<{ characters: string[]; count: number }>('/characters/extract', { text }),

  delete: (id: number) => api.delete(`/characters/${id}`),

  deleteByChar: (char: string) => api.delete(`/characters/by-char/${encodeURIComponent(char)}`),
}

// ===== Articles =====
export interface ArticleResponse {
  id: number
  record_date: string
  topic: string
  content: string
  character_count: number
  source: string
  category: string
  created_at: string
}

export interface PinyinToken {
  char: string
  pinyin: string
  word_len?: number  // >0 = 多字词首字，值为词语长度
}

export interface CharBreakdown {
  total: number
  from_target: string[]
  from_scout: string[]
  from_ally: string[]
  from_lost: string[]
  not_in_any: string[]
}

export interface ArticleWithPinyin {
  id: number
  record_date: string
  topic: string
  content: string
  character_count: number
  source: string
  category: string
  created_at: string | null
  image_url: string | null
  images: { url: string; after_para: number }[]
  paragraphs: PinyinToken[][]
  char_breakdown?: CharBreakdown
  series_id?: number | null
  chapter_number?: number | null
}

export interface LearnedCharsByDate {
  article_date: string
  article_topic: string
  total_in_article: number
  learned_count: number
  not_learned_count: number
  by_date: Record<string, Array<{ character: string; pinyin: string | null }>>
  not_learned: string[]
}

export const articlesApi = {
  generate: (data: { record_date: string; topic: string; characters: string[]; min_chars?: number; max_chars?: number; category?: string; memory_context?: string }) =>
    api.post<ArticleWithPinyin>('/articles/generate', data),

  generateImages: (articleId: number) =>
    api.post<{ id: number; images: { url: string; after_para: number }[] }>(`/articles/${articleId}/generate-images`, {}, { timeout: 300000 }),

  create: (data: { record_date: string; topic: string; content: string; source?: string }) =>
    api.post<ArticleResponse>('/articles/', data),

  list: () => api.get<ArticleResponse[]>('/articles/'),

  getToday: () => api.get<ArticleWithPinyin | null>('/articles/today'),

  getByDate: (date: string) => api.get<ArticleWithPinyin>(`/articles/${date}`),

  getWithPinyin: (id: number) => api.get<ArticleWithPinyin>(`/articles/${id}/pinyin`),

  getLearnedChars: (date: string) => api.get<LearnedCharsByDate>(`/dashboard/article-review/${date}`),

  annotateText: (text: string) => api.post<{ paragraphs: PinyinToken[][]; total_chars: number }>('/articles/pinyin', { text }),

  revise: (id: number, suggestions: string) =>
    api.post<ArticleWithPinyin>(`/articles/${id}/revise`, { suggestions }),

  delete: (id: number) => api.delete(`/articles/${id}`),

  getSeries: (seriesId: number) => api.get<any>(`/articles/series/${seriesId}`),

  getSeriesChapter: (seriesId: number, chapterNumber: number) =>
    api.get<ArticleWithPinyin & { series_id: number; chapter_number: number }>(`/articles/series/${seriesId}/chapter/${chapterNumber}`),
}

// ===== Review =====
export interface ForgottenResponse {
  id: number
  character: string
  pinyin: string | null
  forget_count: number
  first_forgotten_date: string | null
  last_forgotten_date: string | null
  level: string
  learned_days_ago: number | null
}

export interface ForgottenListResponse {
  total: number
  items: ForgottenResponse[]
  level_counts: Record<string, number>
}

export const reviewApi = {
  recordForgotten: (data: { date: string; characters: string[]; pinyin?: string[]; learned_days_ago?: (number | null)[] }) =>
    api.post('/review/forgotten', data),

  listForgotten: (level?: string) =>
    api.get<ForgottenListResponse>('/review/forgotten', { params: level ? { level } : {} }),

  markLearned: (id: number) => api.post(`/review/forgotten/${id}/learned`),

  getStats: () => api.get<Record<string, number>>('/review/stats'),
}

// ===== Dashboard =====
export interface DashboardResponse {
  today: string
  today_characters: string[]
  today_math_characters: string[]
  today_article: (ArticleWithPinyin & { char_breakdown?: CharBreakdown }) | null
  forgotten_stats: Record<string, number>
  total_characters_learned: number
  total_math_characters: number
  recent_questions: CuriosityEventResponse[]
  hot_interests: InterestEvolutionResponse[]
}

export interface StatsResponse {
  total_characters_learned: number
  total_days: number
  daily_progress: Array<{ date: string; count: number; total: number }>
  forgotten_stats: Record<string, number>
  total_forgotten: number
  total_articles: number
  articles: Array<{ date: string; topic: string; character_count: number; source: string }>
}

export const dashboardApi = {
  get: () => api.get<DashboardResponse>('/dashboard/'),
  getStats: () => api.get<StatsResponse>('/dashboard/stats'),
  exportCsv: () => '/api/dashboard/export/csv',
  exportJson: () => '/api/dashboard/export/json',
}

// ===== Curiosity Events =====
export interface CuriosityEventResponse {
  id: number
  event_date: string
  raw_text: string
  cleaned_text: string | null
  keywords_json: string[] | null
  tags_json: string[] | null
  is_answered: boolean
  linked_article_id: number | null
  parent_event_id: number | null
  created_at: string
}

export interface CuriosityListResponse {
  total: number
  unanswered: number
  items: CuriosityEventResponse[]
  tags_summary: Record<string, number>
}

export interface InterestEvolutionResponse {
  id: number
  tag_name: string
  first_mentioned_date: string | null
  last_mentioned_date: string | null
  mention_count: number
  intensity_score: number | null
  trend: string | null
}

export interface TopicSuggestionResponse {
  from_unanswered: Array<{ id: number; event_date: string; raw_text: string; tags: string[] }>
  from_hot_interests: Array<{ tag_name: string; mention_count: number; intensity_score: number }>
  from_declining: Array<{ tag_name: string; mention_count: number }>
}

export const curiosityApi = {
  createEvent: (data: {
    event_date: string
    raw_text: string
    cleaned_text?: string
    keywords?: string[]
    tags?: string[]
    parent_event_id?: number
  }) => api.post<CuriosityEventResponse>('/curiosity/events', data),

  listEvents: (params?: { answered?: boolean; tag?: string; limit?: number; offset?: number }) =>
    api.get<CuriosityListResponse>('/curiosity/events', { params }),

  getEvent: (id: number) => api.get<CuriosityEventResponse>(`/curiosity/events/${id}`),

  updateEvent: (id: number, data: Record<string, any>) =>
    api.patch<CuriosityEventResponse>(`/curiosity/events/${id}`, data),

  linkArticle: (eventId: number, articleId: number) =>
    api.post<CuriosityEventResponse>(`/curiosity/events/${eventId}/link-article/${articleId}`),

  deleteEvent: (id: number) => api.delete(`/curiosity/events/${id}`),

  getThread: (id: number) => api.get<CuriosityEventResponse[]>(`/curiosity/events/${id}/thread`),

  listInterests: (params?: { trend?: string; min_intensity?: number }) =>
    api.get<InterestEvolutionResponse[]>('/curiosity/interests', { params }),

  getHotInterests: (limit?: number) =>
    api.get<InterestEvolutionResponse[]>('/curiosity/interests/hot', { params: { limit } }),

  generateAnswer: (eventId: number) =>
    api.post<{ event: CuriosityEventResponse; article: any }>(`/curiosity/events/${eventId}/generate-answer`),

  getSuggestions: () => api.get<TopicSuggestionResponse>('/curiosity/suggestions'),

  getBadge: () => api.get<{ unanswered_count: number }>('/curiosity/badge'),
}

// ===== Knowledge Graph =====
export interface KnowledgeNodeResponse {
  id: number
  node_name: string
  category: string | null
  first_appearance_date: string | null
  last_review_date: string | null
  total_articles: number
}

export interface KnowledgeLinkResponse {
  id: number
  node_a_id: number
  node_b_id: number
  link_type: string
  strength: number
  discovered_date: string | null
}

export interface KnowledgeGraphResponse {
  nodes: KnowledgeNodeResponse[]
  links: KnowledgeLinkResponse[]
}

export const knowledgeApi = {
  createNode: (data: { node_name: string; category?: string }) =>
    api.post<KnowledgeNodeResponse>('/knowledge/nodes', data),

  listNodes: (category?: string) =>
    api.get<KnowledgeNodeResponse[]>('/knowledge/nodes', { params: category ? { category } : {} }),

  getNode: (id: number) => api.get<KnowledgeNodeResponse>(`/knowledge/nodes/${id}`),

  setCategory: (id: number, category: string) =>
    api.patch(`/knowledge/nodes/${id}/category`, null, { params: { category } }),

  reviewNode: (id: number) => api.post(`/knowledge/nodes/${id}/review`),

  deleteNode: (id: number) => api.delete(`/knowledge/nodes/${id}`),

  getGraph: () => api.get<KnowledgeGraphResponse>('/knowledge/graph'),

  createLink: (params: { node_a_id: number; node_b_id: number; link_type: string; strength?: number }) =>
    api.post('/knowledge/links', null, { params }),

  deleteLink: (id: number) => api.delete(`/knowledge/links/${id}`),

  getNeighbors: (id: number) => api.get(`/knowledge/nodes/${id}/neighbors`),
}

// ===== Memory Context =====
export interface MemoryContextResponse {
  related_articles: Array<{
    id: number
    record_date: string
    topic: string
    snippet: string
    relevance: number
  }>
  forgotten_chars: Array<{
    character: string
    pinyin: string | null
    forget_count: number
    level: string
  }>
  unanswered_questions: Array<{
    id: number
    event_date: string
    raw_text: string
    tags: string[] | null
  }>
  summary_text: string
  prompt_context: string
  has_memory: boolean
}

export const memoryApi = {
  getContext: (data: { topic: string; characters: string[]; lookback_days?: number }) =>
    api.post<MemoryContextResponse>('/memory/context', data),
}

// ===== Voice Profiles (真人录音) =====
export interface VoiceProfileResponse {
  id: number
  name: string
  sample_path: string | null
  prompt_text: string | null
  char_count: number
  created_at: string
}

export const voiceApi = {
  listProfiles: () => api.get<VoiceProfileResponse[]>('/voice/profiles'),

  createProfile: (name: string) => api.post<VoiceProfileResponse>('/voice/profiles', { name }),

  deleteProfile: (id: number) => api.delete(`/voice/profiles/${id}`),

  // Per-character recording
  uploadCharAudio: (profileId: number, char: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file, 'audio.webm')
    return api.put(`/voice/profiles/${profileId}/chars/${encodeURIComponent(char)}`, fd)
  },

  listRecordedChars: (profileId: number) =>
    api.get<string[]>(`/voice/profiles/${profileId}/chars`),

  deleteCharAudio: (profileId: number, char: string) =>
    api.delete(`/voice/profiles/${profileId}/chars/${encodeURIComponent(char)}`),

  batchCheckChars: (profileId: number, chars: string[]) =>
    api.post<Record<string, boolean>>(`/voice/profiles/${profileId}/batch-check`, { chars }),
}

// ===== ASR 语音识别 (科大讯飞) =====
export const asrApi = {
  recognize: (file: File) => {
    const fd = new FormData()
    fd.append('file', file, 'recording.webm')
    return api.post<{ text: string }>('/asr/recognize', fd)
  },
}

// ===== 学生管理 =====
export interface StudentResponse {
  id: number
  name: string
  avatar: string
  created_at: string
}

export const studentsApi = {
  list: () => api.get<StudentResponse[]>('/students'),
  create: (data: { name: string; avatar?: string }) => api.post<StudentResponse>('/students', data),
  delete: (id: number) => api.delete(`/students/${id}`),
  generateAvatar: (id: number, useGpu: boolean = false) => api.post<{ id: number; name: string; avatar: string }>(`/students/${id}/generate-avatar?use_gpu=${useGpu}`),
}

// ===== 四区字库 =====
export interface ZoneCharItem {
  id: number
  character: string
  pinyin: string | null
  source: string | null
  created_at?: string
}

export interface ScoutCharItem extends ZoneCharItem {
  appeared_in_read_count: number
  never_tapped_in_read_count: number
}

export interface LostCharItem extends ZoneCharItem {
  tap_count: number
  article_count: number
  status: string
}

export interface ZoneSummary {
  target: number
  scout: number
  ally: number
  lost: number
}

export interface DensityTier {
  known_max: number
  art_min: number
  art_max: number
  density: number
  reinforce: number
}

export interface ArticleParamsResponse {
  article_min: number
  article_max: number
  target_density: number
  reinforce_density: number
  target_chars: string[]
  reinforce_chars: string[]
  familiar_chars: string[]
  known_count: number
  target_count: number
  scout_count: number
  ally_count: number
  lost_count: number
  tier_index: number
  has_override: boolean
}

export interface ArticleConfigResponse {
  tiers: DensityTier[]
  max_target_per_article: number
  max_reinforce_per_article: number
  override_min_chars: number | null
  override_max_chars: number | null
  override_density: number | null
  override_reinforce: number | null
  current_params: ArticleParamsResponse
}

export interface ReadingLevelNext {
  level: number
  name: string
  icon: string
  known_required: number
  known_current: number
  articles_required: number
  articles_current: number
}

export interface ReadingLevelResponse {
  level: number
  name: string
  icon: string
  known_count: number
  articles_read: number
  leveled_up_at: string | null
  max_level: number
  next: ReadingLevelNext | null
}

export interface LevelUpResponse {
  promoted: boolean
  old_level?: number
  old_name?: string
  new_level?: number
  new_name?: string
  new_icon?: string
  known_count?: number
  articles_read?: number
  message?: string
  current?: ReadingLevelResponse
}

export const zonesApi = {
  // 教学区
  addTarget: (data: { characters: string[]; pinyin?: string[]; source?: string }) =>
    api.post<{ ok: boolean; count: number }>('/zones/target', data),
  listTarget: () => api.get<ZoneCharItem[]>('/zones/target'),
  deleteTarget: (character: string) => api.delete(`/zones/target/${encodeURIComponent(character)}`),

  // 侦查区
  addScout: (data: { characters: string[]; pinyin?: string[]; source?: string }) =>
    api.post('/zones/scout', data),
  listScout: () => api.get<ScoutCharItem[]>('/zones/scout'),
  deleteScout: (character: string) => api.delete(`/zones/scout/${encodeURIComponent(character)}`),

  // 友军区
  addAlly: (data: { characters: string[]; pinyin?: string[]; source?: string }) =>
    api.post('/zones/ally', data),
  listAlly: () => api.get<ZoneCharItem[]>('/zones/ally'),
  deleteAlly: (character: string) => api.delete(`/zones/ally/${encodeURIComponent(character)}`),

  // 战损区
  listLost: () => api.get<LostCharItem[]>('/zones/lost'),
  recoverLost: (character: string) => api.post(`/zones/lost/${encodeURIComponent(character)}/recover`),

  // 总览
  summary: () => api.get<ZoneSummary>('/zones/summary'),

  // 文章生字密度配置（家长模式）
  getArticleConfig: () => api.get<ArticleConfigResponse>('/zones/article-config'),
  computeArticleParams: (override?: { min_chars?: number; max_chars?: number; density?: number; reinforce?: number }) =>
    api.post<ArticleParamsResponse>('/zones/article-params', { override }),

  // 根据密度自动推荐生字并生成文章
  autoGenerate: (data: { topic: string; category?: string; override?: { min_chars?: number; max_chars?: number; density?: number; reinforce?: number } }) =>
    api.post<ArticleWithPinyin>('/zones/auto-generate', data),

  // 阅读等级
  getReadingLevel: () => api.get<ReadingLevelResponse>('/zones/reading-level'),
  checkLevelUp: () => api.post<LevelUpResponse>('/zones/reading-level/check'),
}

// ===== 文章阅读状态 =====
export interface ArticleReadStatus {
  id: number
  article_id: number
  status: 'unread' | 'reading' | 'read'
  read_paragraph_count: number
  total_paragraph_count: number
  started_at: string | null
  finished_at: string | null
}

export const readStatusApi = {
  update: (articleId: number, data: { status: string; read_count: number; total_count: number }) =>
    api.post(`/articles/${articleId}/read-status`, data),
  get: (articleId: number) => api.get<ArticleReadStatus>(`/articles/${articleId}/read-status`),
  batchGet: (articleIds: number[]) =>
    api.get<Record<string, string>>('/articles/read-statuses', { params: { ids: articleIds.join(',') } }),
}

// ===== 阅读行为上报 (隐式反馈) =====
export const behaviorApi = {
  report: (data: { article_id: number; character?: string; action_type: string }) =>
    api.post('/reading-behaviors', data),
}

// ===== 难度反馈 (认知水平校准) =====
export const feedbackApi = {
  submit: (data: { article_id: number; feedback: string; topic: string }) =>
    api.post('/curiosity/feedback', data),
}

// ===== 好奇心对话 =====
export const conversationApi = {
  start: (eventId: number) =>
    api.post<{ session_id: number; reply: string; turn_count: number; cognition_level: number }>(
      `/curiosity/conversation/start?event_id=${eventId}`),

  turn: (sessionId: number, userInput: string) =>
    api.post<{ session_id: number; reply: string; turn_count: number; cognition_level: number }>(
      '/curiosity/conversation/turn', { session_id: sessionId, user_input: userInput }),

  generateArticle: (sessionId: number) =>
    api.post<{ article: any; turn_count: number }>(
      `/curiosity/conversation/generate-article?session_id=${sessionId}`),
}

// ===== 好奇心答案生成 (LangGraph 状态图 API) =====
export interface SeriesInfo {
  series_id: number
  total_chapters: number
  current_chapter: number
  chapter_titles: Array<{ ch: number; title: string; summary: string }>
  article_id?: number
  article_content?: string
  paragraphs?: any
  completed?: boolean
  status?: string
}

export const answerApi = {
  oneShot: (eventId: number) =>
    api.post<{ article_id: number; article_content: string; paragraphs: any }>(
      `/curiosity/answer/${eventId}`),

  conversationStart: (eventId: number) =>
    api.post<{ session_id: number; reply: string; cognition_level: number }>(
      `/curiosity/answer/${eventId}/conversation/start`),

  conversationTurn: (eventId: number, userInput: string) =>
    api.post<{ session_id: number; reply: string; cognition_level: number }>(
      `/curiosity/answer/${eventId}/conversation/turn`, { user_input: userInput }),

  conversationGenerate: (eventId: number) =>
    api.post<{ article_id: number; article_content: string; paragraphs: any }>(
      `/curiosity/answer/${eventId}/conversation/generate`),

  seriesStart: (eventId: number) =>
    api.post<SeriesInfo>(`/curiosity/answer/${eventId}/series/start`),

  seriesNext: (eventId: number, wantNext: boolean) =>
    api.post<SeriesInfo>(`/curiosity/answer/${eventId}/series/next`, { want_next: wantNext }),
}

// ===== 知识库 =====
export interface KnowledgeEntryResponse {
  id: number
  category: string
  subject: string
  grade_level: string
  textbook_version: string
  lesson: string
  title: string
  content: string
  keywords_json: string[] | null
  source: string
  auto_approved: boolean
  used_count: number
}

export interface TextbookConfigResponse {
  configured: boolean
  id?: number
  textbook_version?: string
  current_grade?: string
  current_semester?: string
}

export const knowledgeBaseApi = {
  getConfig: () => api.get<TextbookConfigResponse>('/knowledge-base/config'),

  setup: (data: { textbook_version: string; current_grade: string; current_semester: string }) =>
    api.post('/knowledge-base/config', data),

  search: (params: { q?: string; tags?: string; limit?: number }) =>
    api.get<KnowledgeEntryResponse[]>('/knowledge-base/search', { params }),

  getSchool: () => api.get<KnowledgeEntryResponse[]>('/knowledge-base/school'),

  getExtracurricular: (tags?: string) =>
    api.get<KnowledgeEntryResponse[]>('/knowledge-base/extracurricular', { params: tags ? { tags } : {} }),

  getContext: (params: { topic?: string; characters?: string; tags?: string }) =>
    api.get<{ context: string; has_knowledge: boolean }>('/knowledge-base/context', { params }),

  toggleApprove: (id: number, approved: boolean) =>
    api.patch(`/knowledge-base/entries/${id}/approve?approved=${approved}`),

  createManual: (data: { subject: string; content: string }) =>
    api.post<KnowledgeEntryResponse>('/knowledge-base/entries/manual', data),
}
