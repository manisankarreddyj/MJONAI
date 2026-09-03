'use client'

import { useState, useEffect, useRef } from 'react'
import NavBar from '@/components/NavBar'
import { chatWithAssistant, getChatHistory, getSuggestions } from '@/lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Load initial data
    async function init() {
      const [history, sugg] = await Promise.all([
        getChatHistory(10),
        getSuggestions(),
      ])

      if (history?.conversations) {
        const msgs: Message[] = []
        // Reverse to show oldest first
        const convs = [...(history.conversations || [])].reverse()
        convs.forEach((c: any) => {
          msgs.push({
            role: 'user',
            content: c.message,
            timestamp: new Date(c.created_at)
          })
          msgs.push({
            role: 'assistant',
            content: c.response,
            timestamp: new Date(c.created_at)
          })
        })
        setMessages(msgs)
      } else {
        // Welcome message
        setMessages([{
          role: 'assistant',
          content: 'Namaste! I am ArthAI, your personal trading intelligence. ' +
                   'I analyze markets, explain signals, and help you become a better trader. ' +
                   'What would you like to know today?',
          timestamp: new Date()
        }])
      }

      if (sugg?.suggestions) {
        setSuggestions(sugg.suggestions)
      }
    }
    init()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(text?: string) {
    const messageText = text || input.trim()
    if (!messageText || loading) return

    setInput('')
    setMessages(prev => [...prev, {
      role: 'user',
      content: messageText,
      timestamp: new Date()
    }])
    setLoading(true)

    const response = await chatWithAssistant(messageText)

    setMessages(prev => [...prev, {
      role: 'assistant',
      content: response?.response || 'ArthAI is thinking... Please try again.',
      timestamp: new Date()
    }])
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-arthai-dark flex flex-col">
      <NavBar />
      
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-6 flex flex-col">
        <h1 className="text-2xl font-bold text-white mb-6">
          ArthAI Assistant 🤖
        </h1>

        {/* Messages */}
        <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl 
                      p-4 mb-4 overflow-y-auto min-h-96 max-h-[500px]">
          {messages.map((msg, idx) => (
            <div key={idx}
                 className={`flex mb-4 animate-fade-in
                            ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-xl px-4 py-3 
                             ${msg.role === 'user'
                               ? 'bg-blue-600 text-white'
                               : 'bg-gray-800 text-gray-200'
                             }`}>
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-1 mb-1">
                    <span className="text-blue-400 text-xs font-semibold">ArthAI</span>
                  </div>
                )}
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
                <p className="text-xs opacity-50 mt-1">
                  {msg.timestamp.toLocaleTimeString('en-IN', {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </p>
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-800 rounded-xl px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" 
                       style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" 
                       style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" 
                       style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions */}
        {suggestions.length > 0 && messages.length <= 2 && (
          <div className="mb-4">
            <p className="text-xs text-gray-500 mb-2">Suggested questions:</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.slice(0, 4).map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => sendMessage(s)}
                  className="text-xs px-3 py-1.5 bg-gray-900 border border-gray-700 
                           rounded-full text-gray-300 hover:text-white hover:border-blue-600
                           transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            placeholder="Ask ArthAI anything about markets..."
            className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3
                     text-white text-sm placeholder-gray-500 focus:outline-none
                     focus:border-blue-600 transition-colors"
            disabled={loading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium
                     hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}