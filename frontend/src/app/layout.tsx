import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Trace — AI Agent Security Execution Layer',
  description:
    'Find customers, onboard agent workflows and execute approved security fixes with a complete audit trail.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}
