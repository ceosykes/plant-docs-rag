// Look inside a run: what the router did, what each agent saw, and what it cost.
import { useEffect, useState } from 'react'
import { getRuns, getSelfCheck, getThreads, BASE } from './api'
import type { Chunk, Gate, ModelCall, Run, ThreadSummary } from './types'
import { Card, Fold, Pill } from './ui'

export default function Evaluation() {
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [pickedId, setPickedId] = useState(() => new URLSearchParams(window.location.search).get('thread') || '')

  useEffect(() => {
    getThreads().then(setThreads).catch(() => {})
    if (pickedId) getRuns(pickedId).then(setRuns).catch(() => setRuns([]))
  }, [])

  function pick(id: string) {
    setPickedId(id)
    getRuns(id).then(setRuns).catch(() => setRuns([]))
  }

  return (
    <div>
      <SelfCheckPanel />
      <div className="split">
        <div className="left">
          <h3>Chats</h3>
          {threads.map((t) => (
            <button type="button" key={t.thread_id} className={t.thread_id === pickedId ? 'listrow on' : 'listrow'} onClick={() => pick(t.thread_id)}>
              <span className="mono">{t.thread_id}</span>
              <span>{t.first_question}</span>
              <span><span className="step">{t.status}</span> {t.turns} turn{t.turns === 1 ? '' : 's'}</span>
            </button>
          ))}
        </div>
        <div className="right">
          {pickedId && runs.length === 0 && <p className="muted">No runs found for this chat.</p>}
          {runs.map((r, i) => <RunView key={i} run={r} />)}
        </div>
      </div>
    </div>
  )
}

function SelfCheckPanel() {
  const [gates, setGates] = useState<Gate[] | null>(null)
  const [busy, setBusy] = useState(false)

  async function run() {
    setBusy(true)
    try { setGates((await getSelfCheck()).gates) } catch { setGates([]) }
    setBusy(false)
  }

  return (
    <div className="selfcheck">
      <button type="button" onClick={run} disabled={busy}>{busy ? 'Checking...' : 'Run self-check'}</button>
      {gates && gates.map((g, i) => (
        <div key={i} className="gate">
          <span className={g.passed ? 'good' : 'bad'}>{g.passed ? '✔' : '✘'}</span>
          <span>{g.plain}</span>
          <span className="mono">{String(g.number)}</span>
        </div>
      ))}
    </div>
  )
}

function RunView({ run }: { run: Run }) {
  const byManager = run.answer.status === 'answered_by_manager'
  return (
    <div className="run">
      <p className="question">{run.question}</p>
      <RouterCard run={run} />
      {Object.entries(run.retrieved).map(([corpus, chunks]) => <ChunkCard key={corpus} corpus={corpus} chunks={chunks} />)}
      {run.dropped_quotes.length > 0 && (
        <div className="dropbox">
          <strong>Quotes dropped</strong>
          {run.dropped_quotes.map((d, i) => (
            <div key={i}><Pill name={d.corpus} /> <em>"{d.quote}"</em> <span className="muted">{d.reason} (chunk {d.chunk_id})</span></div>
          ))}
        </div>
      )}
      <CallsTable calls={run.model_calls} />
      <div className="answer">
        <Pill name={byManager ? 'manager' : 'customer'} />
        <p>{run.answer.text}</p>
      </div>
    </div>
  )
}

function RouterCard({ run }: { run: Run }) {
  return (
    <Card name="router">
      <Pill name="router" /> {run.router.corpora.map((c) => <Pill key={c} name={c} />)}
      <p className="muted">{run.router.reason}</p>
      {Object.entries(run.router.queries).map(([c, q]) => (
        <div key={c}><Pill name={c} /> searched for: <span className="mono">{q}</span></div>
      ))}
    </Card>
  )
}

function ChunkCard({ corpus, chunks }: { corpus: string; chunks: Chunk[] }) {
  return (
    <Card name={corpus}>
      <Pill name={corpus} /> <span className="muted">{chunks.length} chunks handed over</span>
      {chunks.map((c, i) => <ChunkRow key={c.id} c={c} rank={i + 1} />)}
    </Card>
  )
}

function ChunkRow({ c, rank }: { c: Chunk; rank: number }) {
  const short = c.text && c.text.length > 400 ? c.text.slice(0, 400) + '...' : c.text
  return (
    <div className="chunk">
      <div>
        <strong>{rank}. <a href={docLink(c)} target="_blank" rel="noreferrer">{c.title}, {c.locator}</a></strong>, {c.doc_date}
        {c.source_url && <> · <a href={c.source_url} target="_blank" rel="noreferrer">publisher's copy</a></>}
        <span className="muted"> score {c.score.toFixed(3)} <small>(dense {c.dense.toFixed(3)}, bm25 {c.bm25.toFixed(3)})</small></span>
      </div>
      {short && <Fold title="Text"><p className="pre">{short}</p></Fold>}
    </div>
  )
}

function CallsTable({ calls }: { calls: ModelCall[] }) {
  return (
    <div className="scroll">
      <table>
        <thead><tr><th>Agent</th><th>Seconds</th><th>Tokens in</th><th>Tokens out</th><th>What it said</th></tr></thead>
        <tbody>
          {calls.map((m, i) => (
            <tr key={i}>
              <td><Pill name={m.corpus || m.node} text={m.node} /></td>
              <td>{m.seconds.toFixed(1)}</td>
              <td>{m.input_tokens}</td>
              <td>{m.output_tokens}</td>
              <td><Fold title="Show"><p className="pre">{m.response_text}</p></Fold></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


// Link to the real page of the real document. Older run records have no source field, so fall back to the id.
function docLink(c: { id: string; locator: string; source?: string }): string {
  const source = c.source || c.id.split('::')[0]
  const m = c.locator.match(/page (\d+)/)
  return `${BASE}/doc/${encodeURIComponent(source)}#page=${m ? m[1] : '1'}`
}
