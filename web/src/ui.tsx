// Tiny shared pieces: a colored pill, a colored card, a fold-out section.
import { useState, type ReactNode } from 'react'
import { colorFor, labelFor } from './colors'

export function Pill({ name, text }: { name: string; text?: string }) {
  return <span className="pill" style={{ background: colorFor(name) }}>{text ?? labelFor(name)}</span>
}

export function Card({ name, children }: { name: string; children: ReactNode }) {
  return <div className="card" style={{ borderLeftColor: colorFor(name) }}>{children}</div>
}

export function Fold({ title, children, open = false }: { title: string; children: ReactNode; open?: boolean }) {
  const [show, setShow] = useState(open)
  return (
    <div className="fold">
      <button type="button" className="fold-btn" onClick={() => setShow(!show)}>
        {show ? '▾' : '▸'} {title}
      </button>
      {show && <div className="fold-body">{children}</div>}
    </div>
  )
}

export function when(iso: string): string {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString()
}
