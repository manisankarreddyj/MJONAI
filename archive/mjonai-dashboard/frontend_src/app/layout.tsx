import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ArthAI - Trading Intelligence',
  description: 'AI Powered Personal Trading Intelligence System',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-arthai-dark text-white min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}