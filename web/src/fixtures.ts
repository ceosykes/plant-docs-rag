// Example data so the screens can be built before the API is up.
import type { Answer, Escalation, ManagerDecision, Run, SelfCheck, Thread, ThreadSummary } from './types'

export const fixtureAnswer: Answer = {
  thread_id: 't-fixture1',
  status: 'answered',
  text: 'Lock out the machine before you clear a jam. Only the person who put the lock on may take it off.',
  corpora_chosen: ['safety', 'maintenance'],
  router_reason: 'The question is about clearing a jam, which touches safety rules and machine upkeep.',
  reports: [
    {
      corpus: 'safety',
      refused: false,
      reasoning: 'Looked for lockout rules. Found the OSHA line on who removes a lock.',
      chunks_seen: 6,
      findings: [
        {
          corpus: 'safety',
          quote: 'Each lockout or tagout device shall be removed by the employee who applied the device.',
          source: 'osha3120_lockout_tagout.pdf',
          title: 'OSHA 3120 Lockout Tagout',
          locator: 'page 12',
          doc_date: '2002 (Revised)',
          why_it_matters: 'Says who may remove the lock.',
          verified: true,
        },
        {
          corpus: 'safety',
          quote: 'This quote was not in the chunk word for word.',
          source: 'osha3120_lockout_tagout.pdf',
          title: 'OSHA 3120 Lockout Tagout',
          locator: 'page 14',
          doc_date: '2002 (Revised)',
          why_it_matters: 'Would have backed the lock rule.',
          verified: false,
        },
      ],
    },
    {
      corpus: 'maintenance',
      refused: true,
      reasoning: 'Searched for jam clearing steps. Nothing in the maintenance manuals matched.',
      chunks_seen: 4,
      findings: [],
    },
  ],
  memory_used: ['Manager Dana said on t-old1: keep the line down until a second person checks the lock.'],
  steps_ran: ['router', 'safety_specialist', 'maintenance_specialist', 'customer_service', 'verify'],
  answered_at: '2026-09-11T15:00:00Z',
}

export const fixtureWaiting: Answer = {
  ...fixtureAnswer,
  status: 'waiting_for_manager',
  text: 'This one needs a person. I sent it to your manager.',
}

export const fixtureThread: Thread = {
  thread_id: 't-fixture1',
  waiting: false,
  turns: [{ question: 'Can I clear a jam on line 3 without locking it out?', answer: fixtureAnswer }],
}

export const fixtureEscalations: Escalation[] = [
  { thread_id: 't-fixture2', question: 'Can we run the press with the guard door open for one shift?', asked_at: '2026-09-11T15:10:00Z' },
]

export const fixtureMemory: ManagerDecision[] = [
  {
    thread_id: 't-old1',
    question: 'Can one person restart line 2 after a lockout?',
    answer: 'No. Two people check the lock first.',
    reason: 'We had a near miss last spring when one person restarted alone.',
    decided_by: 'Dana',
    decided_at: '2026-09-10T09:00:00Z',
  },
]

export const fixtureThreads: ThreadSummary[] = [
  { thread_id: 't-fixture1', first_question: 'Can I clear a jam on line 3 without locking it out?', status: 'answered', turns: 1, asked_at: '2026-09-11T15:00:00Z' },
  { thread_id: 't-fixture2', first_question: 'Can we run the press with the guard door open for one shift?', status: 'waiting_for_manager', turns: 1, asked_at: '2026-09-11T15:10:00Z' },
]

export const fixtureRuns: Run[] = [
  {
    event: 'run',
    thread_id: 't-fixture1',
    question: 'Can I clear a jam on line 3 without locking it out?',
    router: {
      corpora: ['safety', 'maintenance'],
      queries: { safety: 'lockout tagout clearing jam', maintenance: 'line 3 jam clearing steps' },
      reason: 'The question is about clearing a jam, which touches safety rules and machine upkeep.',
    },
    retrieved: {
      safety: [
        { id: 'osha-12', title: 'OSHA 3120 Lockout Tagout', locator: 'page 12', doc_date: '2002 (Revised)', score: 0.81, dense: 0.77, bm25: 0.9, text: 'Each lockout or tagout device shall be removed by the employee who applied the device. When the authorized employee who applied the lockout or tagout device is not available to remove it, that device may be removed under the direction of the employer.' },
        { id: 'osha-14', title: 'OSHA 3120 Lockout Tagout', locator: 'page 14', doc_date: '2002 (Revised)', score: 0.62, dense: 0.6, bm25: 0.65 },
      ],
      maintenance: [
        { id: 'mm-3', title: 'Line 3 Press Manual', locator: 'section 4.1', doc_date: '2019', score: 0.41, dense: 0.44, bm25: 0.3, text: 'Weekly greasing points are listed in table 4.' },
      ],
    },
    dropped_quotes: [
      { corpus: 'safety', chunk_id: 'osha-14', quote: 'This quote was not in the chunk word for word.', reason: 'quote not found in chunk' },
    ],
    model_calls: [
      { node: 'router', corpus: '', response_text: '{"corpora": ["safety", "maintenance"]}', input_tokens: 420, output_tokens: 60, seconds: 0.9 },
      { node: 'safety_specialist', corpus: 'safety', response_text: 'Found the lock removal rule on page 12.', input_tokens: 2100, output_tokens: 240, seconds: 2.4 },
      { node: 'maintenance_specialist', corpus: 'maintenance', response_text: 'NOT_IN_DOCUMENTS', input_tokens: 1500, output_tokens: 12, seconds: 1.1 },
      { node: 'customer_service', corpus: '', response_text: 'Lock out the machine before you clear a jam.', input_tokens: 900, output_tokens: 80, seconds: 1.3 },
    ],
    steps_ran: ['router', 'safety_specialist', 'maintenance_specialist', 'customer_service', 'verify'],
    answer: fixtureAnswer,
  },
]

export const fixtureSelfCheck: SelfCheck = {
  gates: [
    { name: 'index', passed: true, number: 412, plain: 'All documents are indexed.' },
    { name: 'golden', passed: false, number: '0.72', plain: 'The right chunk shows up in the top 5 for 72 percent of test questions.' },
  ],
}

export const fixtureHealth = { ok: true, chunks: 412 }
