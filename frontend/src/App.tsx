import { useState } from 'react'
import { OffersTable } from './components/OffersTable'
import { CandidaturesTable } from './components/CandidaturesTable'
import { ScrapeButton } from './components/ScrapeButton'
import { rescoreAll } from './api'
import { KpiStrip } from './components/KpiStrip'
import { PipelineBoard } from './components/PipelineBoard'

type Tab = 'offers' | 'candidatures'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('offers')
  const [candidatureRefreshKey, setCandidatureRefreshKey] = useState(0)
  const [rescoring, setRescoring] = useState(false)
  const [rescoreToast, setRescoreToast] = useState<string | null>(null)

  function refreshCandidatures() {
    setCandidatureRefreshKey((k) => k + 1)
  }

  async function handleRescore() {
    setRescoring(true)
    try {
      const result = await rescoreAll()
      setRescoreToast(`${result.scored} offre(s) rescorée(s)`)
    } catch (err) {
      setRescoreToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setRescoring(false)
      setTimeout(() => setRescoreToast(null), 3500)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--ui-bg)]">
      <header className="sticky top-0 z-30 border-b border-[var(--ui-border)] bg-white/85 shadow-sm backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-[var(--ui-text)]">mon-ATS</h1>
            <p className="text-xs text-[var(--ui-muted)]">Cockpit candidatures</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                onClick={handleRescore}
                disabled={rescoring}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--ui-border)] px-3 py-1.5 text-sm text-[var(--ui-text)] transition-colors hover:bg-[var(--ui-bg-soft)] disabled:opacity-60"
              >
                {rescoring ? 'Rescoring…' : 'Rescorer'}
              </button>
              {rescoreToast && (
                <div className="absolute right-0 top-10 z-50 w-56 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg">
                  {rescoreToast}
                </div>
              )}
            </div>
            <ScrapeButton onDone={refreshCandidatures} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        <KpiStrip refreshKey={candidatureRefreshKey} />
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <section className="min-w-0 rounded-2xl border border-[var(--ui-border)] bg-white p-4 shadow-sm">
            <div className="mb-4 flex gap-1 rounded-xl bg-[var(--ui-bg-soft)] p-1">
          <button
            onClick={() => setActiveTab('offers')}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'offers'
                    ? 'bg-white text-[var(--ui-brand)] shadow-sm'
                    : 'text-[var(--ui-muted)] hover:text-[var(--ui-text)]'
            }`}
          >
            Offres
          </button>
          <button
            onClick={() => setActiveTab('candidatures')}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'candidatures'
                    ? 'bg-white text-[var(--ui-brand)] shadow-sm'
                    : 'text-[var(--ui-muted)] hover:text-[var(--ui-text)]'
            }`}
          >
            Candidatures
          </button>
        </div>

            <div className="pb-1">
          {activeTab === 'offers' && (
            <OffersTable onCandidatureCreated={refreshCandidatures} />
          )}
          {activeTab === 'candidatures' && (
            <CandidaturesTable refreshKey={candidatureRefreshKey} />
          )}
            </div>
          </section>
          <PipelineBoard refreshKey={candidatureRefreshKey} />
        </div>
      </main>
    </div>
  )
}
