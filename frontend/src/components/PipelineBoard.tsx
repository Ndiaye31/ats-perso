import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { getCandidatures } from '../api'
import type { CandidatureWithOffer } from '../types'
import { StatusBadge } from './StatusBadge'

interface Props {
  refreshKey: number
}

const COLUMNS: Array<{ key: string; title: string }> = [
  { key: 'brouillon', title: 'Brouillon' },
  { key: 'envoyée', title: 'Envoyée' },
  { key: 'relancée', title: 'Relance' },
  { key: 'refusée', title: 'Refusée' },
]

export function PipelineBoard({ refreshKey }: Props) {
  const [items, setItems] = useState<CandidatureWithOffer[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      try {
        const data = await getCandidatures()
        if (!active) return
        setItems(data)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [refreshKey])

  const grouped = useMemo(() => {
    const map: Record<string, CandidatureWithOffer[]> = {}
    for (const col of COLUMNS) map[col.key] = []

    for (const item of items) {
      if (!map[item.statut]) continue
      map[item.statut].push(item)
    }

    return map
  }, [items])

  return (
    <aside className="w-full rounded-2xl border border-[var(--ui-border)] bg-white p-4 shadow-sm xl:self-start">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--ui-text)]">Pipeline candidatures</h3>
        <span className="text-xs text-[var(--ui-muted)]">{items.length} total</span>
      </div>

      {loading && <p className="text-sm text-[var(--ui-muted)]">Chargement du pipeline…</p>}

      {!loading && (
        <div className="space-y-3">
          {COLUMNS.map((col) => {
            const list = grouped[col.key] ?? []
            return (
              <section key={col.key} className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-soft)] p-2.5">
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--ui-muted)]">{col.title}</h4>
                  <span className="text-xs text-[var(--ui-muted)]">{list.length}</span>
                </div>
                <div className="space-y-2">
                  {list.slice(0, 4).map((c) => (
                    <article key={c.id} className="rounded-lg border border-[var(--ui-border)] bg-white p-2">
                      <p className="line-clamp-1 text-xs font-medium text-[var(--ui-text)]">{c.offer_title}</p>
                      <p className="mb-1 line-clamp-1 text-[11px] text-[var(--ui-muted)]">{c.offer_company}</p>
                      <div className="flex items-center justify-between">
                        <StatusBadge status={c.statut} />
                        {c.offer_url && (
                          <a
                            href={c.offer_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-[var(--ui-brand)] hover:underline"
                          >
                            <ArrowUpRight size={12} className="inline" /> Ouvrir
                          </a>
                        )}
                      </div>
                    </article>
                  ))}
                  {list.length === 0 && <p className="text-xs text-[var(--ui-muted)]">Aucun élément</p>}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </aside>
  )
}
