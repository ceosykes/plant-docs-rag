// The manager's screen: answer questions the system could not, and see past decisions.
import { useEffect, useState } from 'react'
import { getEscalations, getMemory, resume } from './api'
import type { Escalation, ManagerDecision } from './types'
import { Pill, when } from './ui'

export default function Manager() {
  const [list, setList] = useState<Escalation[]>([])
  const [memory, setMemory] = useState<ManagerDecision[]>([])
  const [picked, setPicked] = useState<Escalation | null>(null)
  const [sentTo, setSentTo] = useState('')

  function load() {
    getEscalations().then(setList).catch(() => {})
    getMemory().then(setMemory).catch(() => {})
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 10000)
    return () => clearInterval(id)
  }, [])

  function done(threadId: string) {
    setList((old) => old.filter((e) => e.thread_id !== threadId))
    setPicked(null)
    setSentTo(threadId)
    getMemory().then(setMemory).catch(() => {})
  }

  return (
    <div>
      <h3><Pill name="manager" /> Questions waiting for you</h3>
      {sentTo && <p className="good">Sent back to thread {sentTo}</p>}
      {list.length === 0 && <p className="muted">Nothing is waiting right now.</p>}
      {list.map((e) => (
        <button type="button" key={e.thread_id} className="listrow" onClick={() => setPicked(e)}>
          <span className="mono">{e.thread_id}</span>
          <span>{e.question}</span>
          <span className="muted">{when(e.asked_at)}</span>
        </button>
      ))}
      {picked && <ResumeForm e={picked} onDone={done} />}
      <MemoryTable rows={memory} />
    </div>
  )
}

function ResumeForm({ e, onDone }: { e: Escalation; onDone: (id: string) => void }) {
  const [answer, setAnswer] = useState('')
  const [reason, setReason] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ready = answer.trim() && reason.trim() && name.trim() && !busy

  async function submit() {
    setBusy(true)
    setError('')
    try {
      await resume(e.thread_id, answer.trim(), reason.trim(), name.trim())
      onDone(e.thread_id)
    } catch (err) {
      setError('Could not send. ' + String(err))
    }
    setBusy(false)
  }

  return (
    <div className="card" style={{ borderLeftColor: '#ef6c00' }}>
      <label>The question<input value={e.question} readOnly /></label>
      <label>Your answer<textarea rows={3} value={answer} onChange={(ev) => setAnswer(ev.target.value)} /></label>
      <label>Your reason (why you decided this; it is saved so the next person sees it)
        <textarea rows={3} value={reason} onChange={(ev) => setReason(ev.target.value)} required />
      </label>
      <label>Your name<input value={name} onChange={(ev) => setName(ev.target.value)} /></label>
      <button type="button" onClick={submit} disabled={!ready}>{busy ? 'Sending...' : 'Send answer'}</button>
      {error && <p className="bad">{error}</p>}
    </div>
  )
}

function MemoryTable({ rows }: { rows: ManagerDecision[] }) {
  return (
    <div>
      <h3>What managers have decided so far</h3>
      {rows.length === 0 && <p className="muted">No decisions yet.</p>}
      {rows.length > 0 && (
        <div className="scroll">
          <table>
            <thead><tr><th>When</th><th>Who</th><th>Question</th><th>Answer</th><th>Reason</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{when(r.decided_at)}</td><td>{r.decided_by}</td><td>{r.question}</td><td>{r.answer}</td><td>{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
