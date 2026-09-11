// Mirrors app/contract.py. Field names are exact.
export type Corpus = 'safety' | 'maintenance' | 'quality'
export type Status = 'answered' | 'refused' | 'waiting_for_manager' | 'answered_by_manager'

export interface Finding {
  corpus: Corpus
  quote: string
  source: string
  title: string
  locator: string
  doc_date: string
  why_it_matters: string
  verified: boolean
  source_url?: string
}

export interface SpecialistReport {
  corpus: Corpus
  findings: Finding[]
  refused: boolean
  reasoning: string
  chunks_seen: number
}

export interface Answer {
  thread_id: string
  status: Status
  text: string
  corpora_chosen: Corpus[]
  router_reason: string
  reports: SpecialistReport[]
  memory_used: string[]
  steps_ran: string[]
  answered_at: string
}

export interface ManagerDecision {
  thread_id: string
  question: string
  answer: string
  reason: string
  decided_by: string
  decided_at: string
}

export interface Turn { question: string; answer: Answer }
export interface Thread { thread_id: string; turns: Turn[]; waiting: boolean }
export interface Escalation { thread_id: string; question: string; asked_at: string }
export interface ThreadSummary {
  thread_id: string
  first_question: string
  status: string
  turns: number
  asked_at: string
}

export interface Chunk {
  id: string
  title: string
  locator: string
  doc_date: string
  score: number
  dense: number
  bm25: number
  text?: string
  source?: string
  source_url?: string
}

export interface DroppedQuote { corpus: string; chunk_id: string; quote: string; reason: string }

export interface ModelCall {
  node: string
  corpus: string
  response_text: string
  input_tokens: number
  output_tokens: number
  seconds: number
}

export interface Run {
  event: string
  thread_id: string
  question: string
  router: { corpora: string[]; queries: Record<string, string>; reason: string }
  retrieved: Record<string, Chunk[]>
  dropped_quotes: DroppedQuote[]
  model_calls: ModelCall[]
  steps_ran: string[]
  answer: Answer
}

export interface Gate { name: string; passed: boolean; number: string | number; plain: string }
export interface SelfCheck { gates: Gate[] }
export interface Health { ok: boolean; chunks: number }
