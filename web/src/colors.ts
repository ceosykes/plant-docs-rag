// One color per agent. Used as a pill and as a card's left border.
export const COLORS: Record<string, string> = {
  customer: '#6f42c1',
  safety: '#c62828',
  maintenance: '#1565c0',
  quality: '#2e7d32',
  router: '#455a64',
  manager: '#ef6c00',
}

export const NAMES: Record<string, string> = {
  customer: 'Customer service agent',
  safety: 'Safety agent',
  maintenance: 'Maintenance agent',
  quality: 'Quality agent',
  router: 'Router',
  manager: 'Manager',
}

// Model call node names come in many spellings. Map them to one color key.
export function keyFor(name: string): string {
  const n = (name || '').toLowerCase()
  if (n.includes('safety')) return 'safety'
  if (n.includes('maint')) return 'maintenance'
  if (n.includes('quality')) return 'quality'
  if (n.includes('rout')) return 'router'
  if (n.includes('manager')) return 'manager'
  return 'customer'
}

export function colorFor(name: string): string {
  return COLORS[keyFor(name)]
}

export function labelFor(name: string): string {
  return NAMES[keyFor(name)]
}
