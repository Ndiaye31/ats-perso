import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Briefcase, FileClock, Send, TrendingUp } from 'lucide-react'
import { getCandidatures, getOffersTable } from '../api'
import type { CandidatureWithOffer } from '../types'

interface Props {
  refreshKey: number
}

function KpiCard({
  label,
  value,
  accent,
  icon,
}: {
  label: string
  value: string
  accent: string
  icon: ReactNode
}) {
  return (
    <article className="rounded-xl border border-[var(--ui-border)] bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--ui-muted)]">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--ui-text)]">{value}</p>
        </div>
        <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${accent}`}>
          {icon}
        </span>
      </div>
    </article>
  )
}

export function KpiStrip({ refreshKey }: Props) {
  const [offersTotal, setOffersTotal] = useState<number>(0)
  const [candidatures, setCandidatures] = useState<CandidatureWithOffer[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setLoading(true)
      try {
        const [offers, cands] = await Promise.all([
          getOffersTable({ limit: 1, offset: 0, signal: controller.signal }),
          getCandidatures(),
        ])
        if (controller.signal.aborted) return
        setOffersTotal(offers.total)
        setCandidatures(cands)
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    load()
    return () => controller.abort()
  }, [refreshKey])

  const stats = useMemo(() => {
    const brouillons = candidatures.filter((c) => c.statut === 'brouillon').length
    const envoyees = candidatures.filter((c) => c.statut === 'envoyée').length
    const conversion = candidatures.length
      ? Math.round((envoyees / candidatures.length) * 100)
      : 0

    return {
      offersTotal,
      brouillons,
      envoyees,
      conversion,
    }
  }, [candidatures, offersTotal])

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[94px] animate-pulse rounded-xl border border-[var(--ui-border)] bg-white/80" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        label="Offres disponibles"
        value={String(stats.offersTotal)}
        accent="bg-cyan-100 text-cyan-700"
        icon={<Briefcase size={16} />}
      />
      <KpiCard
        label="Brouillons"
        value={String(stats.brouillons)}
        accent="bg-amber-100 text-amber-700"
        icon={<FileClock size={16} />}
      />
      <KpiCard
        label="Envoyées"
        value={String(stats.envoyees)}
        accent="bg-emerald-100 text-emerald-700"
        icon={<Send size={16} />}
      />
      <KpiCard
        label="Conversion"
        value={`${stats.conversion}%`}
        accent="bg-indigo-100 text-indigo-700"
        icon={<TrendingUp size={16} />}
      />
    </div>
  )
}
