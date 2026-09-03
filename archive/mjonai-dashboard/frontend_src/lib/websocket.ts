/**
 * ArthAI WebSocket Client
 * Real-time updates from backend
 */

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || ""
if (!API_KEY) console.error("NEXT_PUBLIC_API_KEY not set - WS auth will be rejected")

type MessageHandler = (data: any) => void

class ArthAIWebSocket {
  private ws: WebSocket | null = null
  private handlers: Map<string, MessageHandler[]> = new Map()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 3000
  private isConnected = false

  connect() {
    if (typeof window === 'undefined') return
    
    try {
      this.ws = new WebSocket(WS_URL)
      
      this.ws.onopen = () => {
        console.log('ArthAI WebSocket connected')
        // Send auth immediately
        this.ws?.send(JSON.stringify({ api_key: API_KEY }))
      }
      
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'connected') {
            this.isConnected = true
            console.log('ArthAI WebSocket authenticated')
            return
          }
          
          if (data.type === 'heartbeat' || data.type === 'pong') {
            return
          }
          
          // Dispatch to type-specific handlers
          const typeHandlers = this.handlers.get(data.type) || []
          const allHandlers = this.handlers.get('*') || []
          
          ;[...typeHandlers, ...allHandlers].forEach(handler => {
            try {
              handler(data)
            } catch (e) {
              console.error('WebSocket handler error:', e)
            }
          })
        } catch (e) {
          console.error('WebSocket parse error:', e)
        }
      }
      
      this.ws.onclose = () => {
        this.isConnected = false
        console.log('ArthAI WebSocket disconnected, reconnecting...')
        this.scheduleReconnect()
      }
      
      this.ws.onerror = (error) => {
        console.error('ArthAI WebSocket error:', error)
      }
    } catch (e) {
      console.error('WebSocket connection failed:', e)
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.reconnectDelay)
  }

  on(type: string, handler: MessageHandler) {
    const existing = this.handlers.get(type) || []
    this.handlers.set(type, [...existing, handler])
  }

  off(type: string, handler: MessageHandler) {
    const existing = this.handlers.get(type) || []
    this.handlers.set(type, existing.filter(h => h !== handler))
  }

  ping() {
    this.ws?.send(JSON.stringify({ type: 'ping' }))
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
    this.isConnected = false
  }

  get connected() {
    return this.isConnected
  }
}

// Singleton
export const arthaiWS = new ArthAIWebSocket()