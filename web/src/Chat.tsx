// The floor supervisor's screen. Thread id lives in the URL as ?thread=...
import { useEffect, useRef, useState } from 'react'
import { BASE, ask, getThread } from './api'
import type { Answer, Finding, SpecialistReport, Turn } from './types'
import { Card, Fold, Pill } from './ui'

function threadFromUrl(): string {
  const id = new URLSearchParams(window.location.search).get('thread')
  if (id) return id
  const fresh = 't-' + Date.now().toString(36)
  setUrlThread(fresh)
  return fresh
}

function setUrlThread(id: string) {
  const url = new URL(window.location.href)
  url.searchParams.set('thread', id)
  window.history.pushState({}, '', url)
}

export default function Chat() {
  const [threadId, setThreadId] = useState(threadFromUrl)
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getThread(threadId).then((t) => setTurns(t.turns)).catch(() => setTurns([]))
  }, [threadId])

  const waiting = turns.some((t) => t.answer.status === 'waiting_for_manager')
  useEffect(() => {
    if (!waiting) return
    const id = setInterval(() => {
      getThread(threadId).then((t) => { if (!t.waiting) setTurns(t.turns) }).catch(() => {})
    }, 5000)
    return () => clearInterval(id)
  }, [waiting, threadId])

  function newChat() {
    const fresh = 't-' + Date.now().toString(36)
    setUrlThread(fresh)
    setThreadId(fresh)
    setTurns([])
    setError('')
  }

  async function send() {
    const q = text.trim()
    if (!q || busy) return
    setBusy(true)
    setError('')
    try {
      const a = await ask(threadId, q)
      setTurns((old) => [...old, { question: q, answer: a }])
      setText('')
    } catch (e) {
      setError('Something went wrong. ' + String(e))
    }
    setBusy(false)
  }

  const paneRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = paneRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns, busy])

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="chatwin">
      <div className="row chathead">
        <span className="muted">Chat {threadId}</span>
        <button type="button" onClick={newChat}>New chat</button>
      </div>
      <div className="chatpane" ref={paneRef}>
        {turns.length === 0 && !busy && <p className="muted center">Ask a question about safety, a machine, or quality checks.</p>}
        {turns.map((t, i) => <TurnView key={i} turn={t} />)}
        {busy && <div className="bubble bot"><span className="muted">Looking in the documents...</span></div>}
        {error && <div className="bubble bot bad">{error}</div>}
      </div>
      <div className="askbar">
        <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey}
          placeholder="Type your question and press Enter" rows={2} disabled={busy} />
        <button type="button" onClick={send} disabled={busy || !text.trim()}>Ask</button>
      </div>
    </div>
  )
}

function TurnView({ turn }: { turn: Turn }) {
  const a = turn.answer
  return (
    <div className="turn">
      <div className="bubble me">{turn.question}</div>
      <div className="bubble bot">
        {a.status === 'waiting_for_manager' ? <WaitingBox a={a} /> : <AnswerView a={a} />}
      </div>
    </div>
  )
}

function WaitingBox({ a }: { a: Answer }) {
  return (
    <div className="waitbox">
      <p>{a.text}</p>
      <p><strong>Your manager can answer this on the Manager tab.</strong> This page checks back every few seconds.</p>
    </div>
  )
}

function statusLine(s: Answer['status']): string {
  if (s === 'answered_by_manager') return 'Answered by your manager'
  if (s === 'waiting_for_manager') return 'Waiting for your manager'
  if (s === 'refused') return 'Not found in the documents'
  return 'Answered'
}

function AnswerView({ a }: { a: Answer }) {
  const byManager = a.status === 'answered_by_manager'
  return (
    <div>
      <div className="answer">
        {byManager ? <Pill name="manager" /> : <Pill name="customer" />}
        <p>{a.text}</p>
      </div>
      <p className="muted small">{statusLine(a.status)}</p>
      {!byManager && <Sources reports={a.reports} />}
    </div>
  )
}

function Sources({ reports }: { reports: SpecialistReport[] }) {
  if (!reports.length) return null
  const n = reports.reduce((k, r) => k + r.findings.filter((f) => f.verified).length, 0)
  return (
    <Fold title={`Where this came from (${n} ${n === 1 ? 'quote' : 'quotes'})`} open={new URLSearchParams(window.location.search).get('open') === '1'}>
      {reports.map((r) => <ReportCard key={r.corpus} r={r} />)}
    </Fold>
  )
}

function ReportCard({ r }: { r: SpecialistReport }) {
  const good = r.findings.filter((f) => f.verified)
  return (
    <Card name={r.corpus}>
      <Pill name={r.corpus} />
      {r.refused || !good.length
        ? <p className="muted">The {r.corpus} documents did not have this.</p>
        : good.map((f, i) => <FindingView key={i} f={f} />)}
    </Card>
  )
}

function pageNumber(locator: string): string {
  const m = locator.match(/page (\d+)/)
  return m ? m[1] : '1'
}

function FindingView({ f }: { f: Finding }) {
  const local = `${BASE}/doc/${encodeURIComponent(f.source)}#page=${pageNumber(f.locator)}`
  return (
    <div className="finding">
      <em>"{f.quote}"</em>
      <div className="muted">
        <a href={local} target="_blank" rel="noreferrer">{f.title}, {f.locator}</a>, {f.doc_date}
        {f.source_url && <> · <a href={f.source_url} target="_blank" rel="noreferrer">publisher's copy</a></>}
      </div>
    </div>
  )
}
