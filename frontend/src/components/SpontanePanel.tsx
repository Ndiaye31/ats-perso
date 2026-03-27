import { useState, useCallback, useEffect, useRef } from 'react'
import { RefreshCw, Wand2, Send, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  spontaneScrape,
  spontaneGetCibles,
  spontaneGenerateLMBatch,
  spontaneSendBatch,
  type CibleSpontanee,
} from '../api'
import { SpontaneContactModal } from './SpontaneContactModal'

const PAGE_SIZE = 100

type StepStatus = 'idle' | 'loading' | 'done' | 'error'

interface StepResult { label: string; value: string }
interface StepState { status: StepStatus; results: StepResult[]; error: string | null }

const initial: StepState = { status: 'idle', results: [], error: null }

const SECTEUR_LABELS: Record<string, string> = {
  mairies:   'Mairies',
  education: 'Éducation',
}

const STATUT_COLORS: Record<string, string> = {
  neuf:    'bg-gray-100 text-gray-600',
  'prêt':  'bg-amber-100 text-amber-700',
  'envoyé': 'bg-emerald-100 text-emerald-700',
  erreur:  'bg-red-100 text-red-700',
}

export function SpontanePanel() {
  const [step1, setStep1] = useState<StepState>(initial)
  const [step2, setStep2] = useState<StepState>(initial)
  const [step3, setStep3] = useState<StepState>(initial)

  const [secteurFilter, setSecteurFilter] = useState('')
  const [deptFilter, setDeptFilter] = useState('')
  const [showEnvoyes, setShowEnvoyes] = useState(false)

  const [cibles, setCibles] = useState<CibleSpontanee[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const pageRef = useRef(0)

  const [loadingCibles, setLoadingCibles] = useState(false)
  const [selectedCible, setSelectedCible] = useState<CibleSpontanee | null>(null)

  const loadCibles = useCallback(async (p: number) => {
    setLoadingCibles(true)
    try {
      const res = await spontaneGetCibles({
        ...(secteurFilter ? { secteur: secteurFilter } : {}),
        limit: PAGE_SIZE,
        offset: p * PAGE_SIZE,
      })
      setCibles(res.items)
      setTotal(res.total)
      setPage(p)
      pageRef.current = p
    } catch {
      setCibles([])
      setTotal(0)
    } finally {
      setLoadingCibles(false)
    }
  }, [secteurFilter])

  // Recharge page 0 quand le filtre secteur change
  useEffect(() => {
    loadCibles(0)
  }, [loadCibles])

  async function handleScrape() {
    setStep1({ status: 'loading', results: [], error: null })
    try {
      const r = await spontaneScrape(secteurFilter || undefined)
      setStep1({
        status: 'done',
        results: [
          { label: 'Nouvelles cibles', value: String(r.inseres) },
          { label: 'Doublons ignorés', value: String(r.ignores) },
        ],
        error: null,
      })
      await loadCibles(0)
    } catch (e) {
      setStep1({ status: 'error', results: [], error: e instanceof Error ? e.message : String(e) })
    }
  }

  async function handleGenerateLM() {
    setStep2({ status: 'loading', results: [], error: null })
    try {
      const r = await spontaneGenerateLMBatch(secteurFilter || undefined, 30)
      setStep2({
        status: 'done',
        results: [
          { label: 'LM générées', value: String(r.generees) },
          { label: 'Erreurs', value: String(r.erreurs.length) },
        ],
        error: r.erreurs.length > 0 ? r.erreurs.map(e => e.nom).join(', ') : null,
      })
      await loadCibles(pageRef.current)
    } catch (e) {
      setStep2({ status: 'error', results: [], error: e instanceof Error ? e.message : String(e) })
    }
  }

  async function handleSendAll() {
    setStep3({ status: 'loading', results: [], error: null })
    try {
      const r = await spontaneSendBatch({ secteur: secteurFilter || undefined, limit: 30 })
      setStep3({
        status: 'done',
        results: [
          { label: 'Envoyés', value: String(r.envoyes) },
          { label: 'Erreurs', value: String(r.erreurs.length) },
        ],
        error: r.erreurs.length > 0 ? r.erreurs.map(e => e.nom).join(', ') : null,
      })
      await loadCibles(pageRef.current)
    } catch (e) {
      setStep3({ status: 'error', results: [], error: e instanceof Error ? e.message : String(e) })
    }
  }

  // Filtres client sur la page courante
  const ciblesFiltered = cibles
    .filter(c => showEnvoyes || c.statut !== 'envoyé')
    .filter(c => !deptFilter || c.departement === deptFilter)

  const ciblesEnvoyees = cibles.filter(c => c.statut === 'envoyé')
  const ciblesPret = ciblesFiltered.filter(c => c.statut === 'prêt')
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-6">

      {/* Filtres */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[var(--ui-muted)]">Secteur :</span>
          {(['', 'mairies', 'education'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSecteurFilter(s)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                secteurFilter === s
                  ? 'bg-[var(--ui-brand)] text-white'
                  : 'border border-[var(--ui-border)] text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)]'
              }`}
            >
              {s === '' ? 'Tous' : SECTEUR_LABELS[s]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[var(--ui-muted)]">Département :</span>
          <select
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            className="rounded-md border border-[var(--ui-border)] bg-white px-2 py-1 text-xs text-[var(--ui-text)] focus:outline-none"
          >
            <option value="">Tous</option>
            <option value="75">75 — Paris</option>
            <option value="77">77 — Seine-et-Marne</option>
            <option value="91">91 — Essonne</option>
            <option value="93">93 — Seine-Saint-Denis</option>
            <option value="94">94 — Val-de-Marne</option>
          </select>
        </div>
      </div>

      {/* Pipeline */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-[var(--ui-text)]">Pipeline candidatures spontanées</p>
        <Step
          number={1}
          title="Scraper les cibles"
          description="Récupère les mairies et établissements scolaires d'Île-de-France via les APIs officielles."
          state={step1}
          onRun={handleScrape}
          buttonLabel="Lancer le scraping"
        />
        <Step
          number={2}
          title="Générer les lettres de motivation"
          description="Génère une LM personnalisée par secteur pour chaque cible avec email (via Claude)."
          state={step2}
          onRun={handleGenerateLM}
          buttonLabel="Générer les LM"
          disabled={total === 0}
          disabledReason="Lancez d'abord le scraping"
        />
        <Step
          number={3}
          title="Envoyer à toutes les cibles prêtes"
          description="Envoie les candidatures par email (Gmail) avec CV sectoriel en pièce jointe."
          state={step3}
          onRun={handleSendAll}
          buttonLabel="Envoyer à tous"
          disabled={ciblesPret.length === 0 && step2.status !== 'done'}
          disabledReason="Générez d'abord les LM"
        />
      </div>

      {/* Stats */}
      {total > 0 && (
        <div className="flex flex-wrap gap-3">
          <div className="rounded-lg border border-[var(--ui-border)] bg-white px-4 py-2 text-center">
            <p className="text-lg font-bold text-[var(--ui-text)]">{total}</p>
            <p className="text-xs text-[var(--ui-muted)]">Total en base</p>
          </div>
          <div className="rounded-lg border border-[var(--ui-border)] bg-white px-4 py-2 text-center">
            <p className="text-lg font-bold text-amber-700">{ciblesPret.length}</p>
            <p className="text-xs text-[var(--ui-muted)]">Prêtes (page)</p>
          </div>
        </div>
      )}

      {/* Table des cibles */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <p className="text-sm font-medium text-[var(--ui-text)]">
              {ciblesFiltered.length} affichées
              {total > 0 && <span className="ml-1 text-[var(--ui-muted)]">/ {total} en base</span>}
            </p>
            {ciblesEnvoyees.length > 0 && (
              <button
                onClick={() => setShowEnvoyes(v => !v)}
                className="rounded-md border border-[var(--ui-border)] px-2.5 py-1 text-xs text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)]"
              >
                {showEnvoyes ? 'Masquer les envoyées' : `Voir les envoyées (${ciblesEnvoyees.length})`}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {totalPages > 1 && (
              <div className="flex items-center gap-1 text-xs text-[var(--ui-muted)]">
                <button
                  onClick={() => loadCibles(page - 1)}
                  disabled={page === 0 || loadingCibles}
                  className="rounded p-1 hover:bg-[var(--ui-bg-soft)] disabled:opacity-40"
                >
                  <ChevronLeft size={13} />
                </button>
                <span>{page + 1} / {totalPages}</span>
                <button
                  onClick={() => loadCibles(page + 1)}
                  disabled={page >= totalPages - 1 || loadingCibles}
                  className="rounded p-1 hover:bg-[var(--ui-bg-soft)] disabled:opacity-40"
                >
                  <ChevronRight size={13} />
                </button>
              </div>
            )}
            <button
              onClick={() => loadCibles(page)}
              disabled={loadingCibles}
              className="flex items-center gap-1.5 rounded-md border border-[var(--ui-border)] px-2.5 py-1 text-xs text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)] disabled:opacity-50"
            >
              <RefreshCw size={11} className={loadingCibles ? 'animate-spin' : ''} />
              Rafraîchir
            </button>
          </div>
        </div>

        {total === 0 ? (
          <div className="rounded-xl border border-[var(--ui-border)] bg-white p-8 text-center text-sm text-[var(--ui-muted)]">
            Aucune cible — lancez le scraping pour en générer.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-[var(--ui-border)] shadow-sm">
            <table className="min-w-full divide-y divide-[var(--ui-border)] text-sm">
              <thead className="bg-[var(--ui-bg-soft)]">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Organisation</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Secteur</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Dept</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Email</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Statut</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--ui-border)] bg-white">
                {ciblesFiltered.map((c) => (
                  <tr key={c.id} className="transition-colors hover:bg-[var(--ui-bg-soft)]">
                    <td className="max-w-[200px] px-3 py-2 font-medium text-[var(--ui-text)]">
                      <div className="truncate">{c.nom}</div>
                      {c.titre_poste && (
                        <div className="truncate text-xs text-[var(--ui-muted)]">{c.titre_poste}</div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-[var(--ui-bg-soft)] px-2 py-0.5 text-xs text-[var(--ui-muted)]">
                        {SECTEUR_LABELS[c.secteur] ?? c.secteur}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--ui-muted)]">{c.departement ?? '—'}</td>
                    <td className="max-w-[180px] truncate px-3 py-2 text-xs text-[var(--ui-muted)]">
                      {c.email
                        ? <a href={`mailto:${c.email}`} className="hover:text-[var(--ui-brand)] hover:underline">{c.email}</a>
                        : <span className="italic">pas d'email</span>
                      }
                    </td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUT_COLORS[c.statut] ?? 'bg-gray-100 text-gray-600'}`}>
                        {c.statut}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {c.email && c.statut !== 'envoyé' && (
                        <button
                          onClick={() => setSelectedCible(c)}
                          className="flex items-center gap-1 rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)] transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                        >
                          <Wand2 size={11} />
                          <Send size={11} />
                          LM + Envoyer
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedCible && (
        <SpontaneContactModal
          cible={selectedCible}
          onClose={() => setSelectedCible(null)}
          onSent={() => loadCibles(pageRef.current)}
        />
      )}
    </div>
  )
}

// ─── Step component ───────────────────────────────────────────────────────────

interface StepProps {
  number: number
  title: string
  description: string
  state: StepState
  onRun: () => void
  buttonLabel: string
  disabled?: boolean
  disabledReason?: string
}

function Step({ number, title, description, state, onRun, buttonLabel, disabled, disabledReason }: StepProps) {
  const isLoading = state.status === 'loading'
  const isDisabled = disabled || isLoading

  return (
    <div className={`rounded-xl border p-4 transition-colors ${
      state.status === 'done' ? 'border-green-200 bg-green-50'
      : state.status === 'error' ? 'border-red-200 bg-red-50'
      : 'border-[var(--ui-border)] bg-white'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            state.status === 'done' ? 'bg-green-500 text-white'
            : state.status === 'error' ? 'bg-red-500 text-white'
            : 'bg-[var(--ui-brand)] text-white'
          }`}>
            {state.status === 'done' ? '✓' : number}
          </span>
          <div>
            <p className="text-sm font-semibold text-[var(--ui-text)]">{title}</p>
            <p className="text-xs text-[var(--ui-muted)]">{description}</p>
          </div>
        </div>
        <button
          onClick={onRun}
          disabled={isDisabled}
          title={disabled && disabledReason ? disabledReason : undefined}
          className="shrink-0 rounded-lg bg-[var(--ui-brand)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isLoading ? 'En cours…' : buttonLabel}
        </button>
      </div>

      {state.results.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-3 pl-9">
          {state.results.map((r) => (
            <div key={r.label} className="text-xs text-[var(--ui-text)]">
              <span className="font-semibold">{r.value}</span>{' '}
              <span className="text-[var(--ui-muted)]">{r.label}</span>
            </div>
          ))}
        </div>
      )}

      {state.error && (
        <p className="mt-2 pl-9 text-xs text-red-600">{state.error}</p>
      )}
    </div>
  )
}
