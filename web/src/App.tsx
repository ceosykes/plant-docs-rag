import { useEffect, useState } from 'react'
import { getHealth } from './api'
import Chat from './Chat'
import Manager from './Manager'
import Evaluation from './Evaluation'

type Tab = 'chat' | 'manager' | 'evaluation'
const TABS: { id: Tab; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'manager', label: 'Manager' },
  { id: 'evaluation', label: 'Evaluation' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>(() => (new URLSearchParams(window.location.search).get('tab') as Tab) || 'chat')
  const [chunks, setChunks] = useState<number | null>(null)

  useEffect(() => {
    getHealth().then((h) => setChunks(h.chunks)).catch(() => setChunks(null))
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <nav>
          {TABS.map((t) => (
            <button key={t.id} type="button" className={tab === t.id ? 'tab on' : 'tab'} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <span className="health">Docs indexed: {chunks === null ? '?' : chunks}</span>
      </header>
      <main>
        {tab === 'chat' && <Chat />}
        {tab === 'manager' && <Manager />}
        {tab === 'evaluation' && <Evaluation />}
      </main>
    </div>
  )
}
