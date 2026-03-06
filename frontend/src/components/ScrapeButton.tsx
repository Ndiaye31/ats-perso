import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { scrapeAll } from '../api'

interface Props {
  onDone?: () => void
}

export function ScrapeButton({ onDone }: Props) {
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  async function handleClick() {
    setLoading(true)
    setToast(null)
    try {
      const results = await scrapeAll()
      const total = Object.values(results).reduce((acc, r) => acc + r.inserted, 0)
      setToast(`${total} nouvelle(s) offre(s) insérée(s)`)
      onDone?.()
    } catch (err) {
      setToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
      setTimeout(() => setToast(null), 4000)
    }
  }

  return (
    <div className="relative inline-block">
      <button
        onClick={handleClick}
        disabled={loading}
        className="flex items-center gap-2 rounded-lg bg-[var(--ui-brand)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:brightness-110 disabled:opacity-60"
      >
        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        Scraper
      </button>
      {toast && (
        <div className="absolute right-0 top-10 z-50 w-64 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
