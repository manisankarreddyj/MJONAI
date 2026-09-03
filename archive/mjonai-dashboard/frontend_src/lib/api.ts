/**
 * ArthAI API Client
 * All API calls go through this file
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
// No default key: a missing NEXT_PUBLIC_API_KEY must fail loudly, not ship a
// hardcoded secret inside the browser bundle.
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || ''

if (!API_KEY) {
  console.error('NEXT_PUBLIC_API_KEY not set - API calls will be rejected')
}

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
}

async function fetchAPI(endpoint: string, options?: RequestInit) {
  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options?.headers,
      },
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error)
    return null
  }
}

// ─── SIGNALS ──────────────────────────────────────────────────
export const getSignals = (limit = 20) =>
  fetchAPI(`/api/signals?limit=${limit}`)

export const getTodaySignals = () =>
  fetchAPI('/api/signals/today')

export const getSignalStats = () =>
  fetchAPI('/api/signals/stats')

export const getLatestSignal = () =>
  fetchAPI('/api/signals/live')

export const getSignalRejections = (limit = 10) =>
  fetchAPI(`/api/signals/rejections?limit=${limit}`)

// ─── PORTFOLIO ────────────────────────────────────────────────
export const getPortfolio = () =>
  fetchAPI('/api/portfolio')

export const getPortfolioSummary = () =>
  fetchAPI('/api/portfolio/summary')

export const getOpenPositions = () =>
  fetchAPI('/api/portfolio/positions')

// ─── PERFORMANCE ──────────────────────────────────────────────
export const getPerformance = (days = 30) =>
  fetchAPI(`/api/performance?days=${days}`)

export const getPerformanceSummary = () =>
  fetchAPI('/api/performance/summary')

export const getDailyBreakdown = (days = 30) =>
  fetchAPI(`/api/performance/daily?days=${days}`)

export const getPerformanceBySymbol = () =>
  fetchAPI('/api/performance/by-symbol')

// ─── MARKET MOOD ──────────────────────────────────────────────
export const getMarketMood = () =>
  fetchAPI('/api/market-mood')

export const getMoodHistory = (days = 7) =>
  fetchAPI(`/api/market-mood/history?days=${days}`)

export const getVixData = () =>
  fetchAPI('/api/market-mood/vix')

export const getGlobalMarkets = () =>
  fetchAPI('/api/market-mood/global')

export const getMarketRegime = () =>
  fetchAPI('/api/market-mood/regime')

// ─── PAPER TRADING ────────────────────────────────────────────
export const getPaperTrades = (status = 'all', limit = 20) =>
  fetchAPI(`/api/paper-trading?status=${status}&limit=${limit}`)

export const getOpenTrades = () =>
  fetchAPI('/api/paper-trading/open')

export const getClosedTrades = (limit = 20) =>
  fetchAPI(`/api/paper-trading/closed?limit=${limit}`)

export const getTradeStats = () =>
  fetchAPI('/api/paper-trading/stats')

export const getAccuracy = () =>
  fetchAPI('/api/paper-trading/accuracy')

export const closePaperTrade = (symbol: string, reason: string = 'MANUAL_UI_EXIT') =>
  fetchAPI('/api/v1/paper-trading/close', {
    method: 'POST',
    body: JSON.stringify({ symbol, reason }),
  })

// ─── ASSISTANT ────────────────────────────────────────────────
export const chatWithAssistant = (message: string, language = 'en') =>
  fetchAPI('/api/assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ message, language }),
  })

export const getChatHistory = (limit = 10) =>
  fetchAPI(`/api/assistant/history?limit=${limit}`)

export const getSuggestions = () =>
  fetchAPI('/api/assistant/suggestions')

// ─── SYSTEM ───────────────────────────────────────────────────
export const getSystemStatus = () =>
  fetchAPI('/api/system')

export const getPsychologyState = () =>
  fetchAPI('/api/system/psychology')

export const getCapitalInfo = () =>
  fetchAPI('/api/system/capital')

export const getSystemLogs = (limit = 20) =>
  fetchAPI(`/api/system/logs?limit=${limit}`)

// ─── LESSONS ──────────────────────────────────────────────────
export const getTodayLesson = () =>
  fetchAPI('/api/lessons/today')

// ─── WATCHLIST ────────────────────────────────────────────────
export const getWatchlist = () =>
  fetchAPI('/api/watchlist')

export const addToWatchlist = (symbol: string, reason?: string) =>
  fetchAPI('/api/watchlist/add', {
    method: 'POST',
    body: JSON.stringify({ symbol, reason }),
  })

export const removeFromWatchlist = (symbol: string) =>
  fetchAPI(`/api/watchlist/${symbol}`, { method: 'DELETE' })