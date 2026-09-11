// Small fetch helpers. Set VITE_USE_FIXTURES=1 to get example data with no server.
import * as fx from './fixtures'
import type { Answer, Escalation, Health, ManagerDecision, Run, SelfCheck, Thread, ThreadSummary } from './types'

export const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8022'
const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1'

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`GET ${path} failed: ${r.status}`)
  return r.json()
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`POST ${path} failed: ${r.status}`)
  return r.json()
}

export function getHealth(): Promise<Health> {
  if (USE_FIXTURES) return Promise.resolve(fx.fixtureHealth)
  return getJson('/health')
}

export function ask(thread_id: string, text: string): Promise<Answer> {
  if (USE_FIXTURES) return Promise.resolve({ ...fx.fixtureAnswer, thread_id })
  return postJson('/ask', { thread_id, text })
}

export function resume(thread_id: string, answer: string, reason: string, decided_by: string): Promise<Answer> {
  if (USE_FIXTURES) return Promise.resolve({ ...fx.fixtureAnswer, thread_id, status: 'answered_by_manager', text: answer })
  return postJson('/resume', { thread_id, answer, reason, decided_by })
}

export function getThread(thread_id: string): Promise<Thread> {
  if (USE_FIXTURES) return Promise.resolve({ ...fx.fixtureThread, thread_id })
  return getJson(`/thread/${encodeURIComponent(thread_id)}`)
}

export function getEscalations(): Promise<Escalation[]> {
  if (USE_FIXTURES) return Promise.resolve(fx.fixtureEscalations)
  return getJson('/escalations')
}

export function getMemory(): Promise<ManagerDecision[]> {
  if (USE_FIXTURES) return Promise.resolve(fx.fixtureMemory)
  return getJson('/memory')
}

export function getThreads(): Promise<ThreadSummary[]> {
  if (USE_FIXTURES) return Promise.resolve(fx.fixtureThreads)
  return getJson('/threads')
}

export function getRuns(thread_id: string): Promise<Run[]> {
  if (USE_FIXTURES) return Promise.resolve(fx.fixtureRuns)
  return getJson(`/runs/${encodeURIComponent(thread_id)}`)
}

export function getSelfCheck(): Promise<SelfCheck> {
  if (USE_FIXTURES) return Promise.resolve(fx.fixtureSelfCheck)
  return getJson('/internal/selfcheck')
}
