import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, Wand2, Send, FileText, Mail, Loader2, Plus, Pencil, Trash2 } from 'lucide-react'
import type { OfferTableItem } from '../types'
import {
  bulkDeleteOffers,
  bulkGenerateLMAndAutoApply,
  createCandidature,
  deleteOffer,
  generateLM,
  getCandidatureStatusMap,
  getOffersTable,
} from '../api'
import { ScoreBadge } from './ScoreBadge'
import { StatusBadge } from './StatusBadge'
import { ApplyModal } from './ApplyModal'
import { FicheModal } from './FicheModal'
import { OfferFormModal } from './OfferFormModal'

const SCORE_OPTIONS = [0, 20, 40, 60, 80]
const STATUS_OPTIONS = ['all', 'new', 'applied', 'rejected']
const MODE_OPTIONS = [
  { value: 'all', label: 'Tous modes' },
  { value: 'email', label: 'Email' },
  { value: 'fhf', label: 'FHF' },
  { value: 'emploi_territorial', label: 'Emploi-Territorial' },
  { value: 'portail_tiers', label: 'Portail tiers' },
]
const PAGE_SIZE = 20

interface Props {
  onCandidatureCreated: () => void
}

export function OffersTable({ onCandidatureCreated }: Props) {
  const [offers, setOffers] = useState<OfferTableItem[]>([])
  const [loading, setLoading] = useState(true)
  const [minScore, setMinScore] = useState(0)
  const [statusFilter, setStatusFilter] = useState('all')
  const [locationSearch, setLocationSearch] = useState('')
  const [locationQuery, setLocationQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [modeFilter, setModeFilter] = useState('all')
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [applyOffer, setApplyOffer] = useState<OfferTableItem | null>(null)
  const [ficheOffer, setFicheOffer] = useState<OfferTableItem | null>(null)
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchAutoLoading, setBatchAutoLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [candidatureStatuts, setCandidatureStatuts] = useState<Record<string, string>>({})
  const [reloadSeq, setReloadSeq] = useState(0)
  const [formOffer, setFormOffer] = useState<OfferTableItem | null | undefined>(undefined)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [batchDeleting, setBatchDeleting] = useState(false)

  async function loadOffers(signal: AbortSignal) {
    setLoading(true)
    try {
      const data = await getOffersTable({
        minScore,
        status: statusFilter,
        source:
          sourceFilter !== 'all'
            ? sourceFilter
            : modeFilter === 'fhf'
            ? 'emploi.fhf.fr'
            : modeFilter === 'emploi_territorial'
            ? 'emploi-territorial.fr'
            : 'all',
        mode:
          modeFilter === 'fhf' || modeFilter === 'emploi_territorial'
            ? 'plateforme'
            : modeFilter,
        locationQ: locationQuery,
        limit: PAGE_SIZE,
        offset,
        signal,
      })
      if (signal.aborted) return
      setOffers(data.items)
      setTotal(data.total)
    } catch (err) {
      if (!signal.aborted) {
        showToast(`Erreur chargement offres: ${err instanceof Error ? err.message : String(err)}`)
      }
    } finally {
      if (!signal.aborted) setLoading(false)
    }
  }

  async function loadCandidatureStatuts(signal: AbortSignal) {
    try {
      const rows = await getCandidatureStatusMap(signal)
      if (signal.aborted) return
      const map: Record<string, string> = {}
      for (const row of rows) {
        map[row.offer_id] = row.statut
      }
      setCandidatureStatuts(map)
    } catch (err) {
      if (!signal.aborted) {
        showToast(`Erreur statuts candidatures: ${err instanceof Error ? err.message : String(err)}`)
      }
    }
  }

  useEffect(() => {
    const id = setTimeout(() => {
      setLocationQuery(locationSearch.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(id)
  }, [locationSearch])

  useEffect(() => {
    setOffset(0)
  }, [minScore, statusFilter, sourceFilter, modeFilter])

  useEffect(() => {
    const controller = new AbortController()
    loadOffers(controller.signal)
    return () => controller.abort()
  }, [minScore, statusFilter, sourceFilter, modeFilter, locationQuery, offset, reloadSeq])

  useEffect(() => {
    const controller = new AbortController()
    loadCandidatureStatuts(controller.signal)
    return () => controller.abort()
  }, [reloadSeq])

  useEffect(() => {
    setSelected(new Set())
  }, [offers])

  const sources = useMemo(() => {
    const pageSources = new Set(offers.map((o) => o.source_name ?? o.source_id ?? 'unknown'))
    if (sourceFilter !== 'all') pageSources.add(sourceFilter)
    return [...pageSources]
  }, [offers, sourceFilter])

  function toggleSelect(id: string) {
    if (candidatureStatuts[id] === 'envoyée') return
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectableOffers = useMemo(
    () => offers.filter((o) => candidatureStatuts[o.id] !== 'envoyée'),
    [offers, candidatureStatuts],
  )

  function toggleAll() {
    if (selected.size === selectableOffers.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(selectableOffers.map((o) => o.id)))
    }
  }

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3500)
  }

  async function quickGenerate(offer: OfferTableItem) {
    setGeneratingId(offer.id)
    try {
      const cand = await createCandidature(offer.id)
      await generateLM(cand.id)
      showToast('Lettre générée — ouvre l\'offre pour la finaliser')
      onCandidatureCreated()
      setReloadSeq((v) => v + 1)
    } catch (err) {
      showToast(`Erreur génération : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setGeneratingId(null)
    }
  }

  async function batchApply() {
    setBatchLoading(true)
    try {
      await Promise.all([...selected].map((id) => createCandidature(id)))
      showToast(`${selected.size} candidature(s) créée(s) en brouillon`)
      setSelected(new Set())
      onCandidatureCreated()
      setReloadSeq((v) => v + 1)
    } catch (err) {
      showToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBatchLoading(false)
    }
  }

  async function batchGenerateAndAutoApply() {
    setBatchAutoLoading(true)
    try {
      const created = await Promise.all([...selected].map((id) => createCandidature(id)))
      const candidatureIds = created.map((c) => c.id)
      const result = await bulkGenerateLMAndAutoApply(candidatureIds, false, 2)
      showToast(`Traitées: ${result.total} | OK: ${result.success} | KO: ${result.failed}`)
      setSelected(new Set())
      onCandidatureCreated()
      setReloadSeq((v) => v + 1)
    } catch (err) {
      showToast(`Erreur batch auto: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBatchAutoLoading(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Supprimer cette offre ?')) return
    setDeletingId(id)
    try {
      await deleteOffer(id)
      showToast('Offre supprimée')
      setReloadSeq((v) => v + 1)
    } catch (err) {
      showToast(`Erreur suppression : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setDeletingId(null)
    }
  }

  async function batchDelete() {
    if (!confirm(`Supprimer ${selected.size} offre(s) ?`)) return
    setBatchDeleting(true)
    try {
      const result = await bulkDeleteOffers([...selected])
      showToast(`${result.deleted} offre(s) supprimée(s)`)
      setSelected(new Set())
      setReloadSeq((v) => v + 1)
    } catch (err) {
      showToast(`Erreur suppression : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBatchDeleting(false)
    }
  }

  const canPrev = offset > 0
  const canNext = offset + offers.length < total
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-soft)] p-3 lg:grid-cols-6">
        <div className="lg:col-span-2">
          <label className="mb-1 block text-xs text-[var(--ui-muted)]">Score min</label>
          <div className="flex gap-1.5">
            {SCORE_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setMinScore(s)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                  minScore === s
                    ? 'border-[var(--ui-brand)] bg-[var(--ui-brand)] text-white'
                    : 'border-[var(--ui-border)] bg-white text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)]'
                }`}
              >
                {s}+
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-[var(--ui-muted)]">Statut</label>
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full appearance-none rounded-md border border-[var(--ui-border)] bg-white py-1.5 pl-2 pr-7 text-sm text-[var(--ui-text)] focus:outline-none focus:ring-2 focus:ring-cyan-300"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{s === 'all' ? 'Tous statuts' : s}</option>
              ))}
            </select>
            <ChevronDown size={12} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[var(--ui-muted)]" />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-[var(--ui-muted)]">Lieu</label>
          <input
            type="text"
            value={locationSearch}
            onChange={(e) => setLocationSearch(e.target.value)}
            placeholder="Rechercher..."
            className="w-full rounded-md border border-[var(--ui-border)] bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-300"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs text-[var(--ui-muted)]">Mode</label>
          <div className="relative">
            <select
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value)}
              className="w-full appearance-none rounded-md border border-[var(--ui-border)] bg-white py-1.5 pl-2 pr-7 text-sm text-[var(--ui-text)] focus:outline-none focus:ring-2 focus:ring-cyan-300"
            >
              {MODE_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <ChevronDown size={12} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[var(--ui-muted)]" />
          </div>
        </div>

        {sources.length > 1 && (
          <div>
            <label className="mb-1 block text-xs text-[var(--ui-muted)]">Source</label>
            <div className="relative">
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="w-full appearance-none rounded-md border border-[var(--ui-border)] bg-white py-1.5 pl-2 pr-7 text-sm text-[var(--ui-text)] focus:outline-none focus:ring-2 focus:ring-cyan-300"
              >
                <option value="all">Toutes sources</option>
                {sources.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <ChevronDown size={12} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[var(--ui-muted)]" />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-[var(--ui-muted)]">
        <div className="flex items-center gap-3">
          <span>{total} offre(s) au total</span>
          <button
            onClick={() => setFormOffer(null)}
            className="flex items-center gap-1 rounded-md bg-[var(--ui-brand)] px-3 py-1.5 text-xs font-medium text-white hover:brightness-110"
          >
            <Plus size={12} /> Ajouter une offre
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOffset((v) => Math.max(0, v - PAGE_SIZE))}
            disabled={!canPrev || loading}
            className="rounded-md border border-[var(--ui-border)] px-2 py-1 disabled:opacity-50 hover:bg-[var(--ui-bg-soft)]"
          >
            Précédent
          </button>
          <span>Page {currentPage} / {totalPages}</span>
          <button
            onClick={() => setOffset((v) => v + PAGE_SIZE)}
            disabled={!canNext || loading}
            className="rounded-md border border-[var(--ui-border)] px-2 py-1 disabled:opacity-50 hover:bg-[var(--ui-bg-soft)]"
          >
            Suivant
          </button>
        </div>
      </div>

      <div className="space-y-3 md:hidden">
        {loading && <div className="rounded-xl border border-[var(--ui-border)] bg-white p-4 text-sm text-[var(--ui-muted)]">Chargement…</div>}
        {!loading && offers.length === 0 && <div className="rounded-xl border border-[var(--ui-border)] bg-white p-4 text-sm text-[var(--ui-muted)]">Aucune offre trouvée</div>}
        {!loading && offers.map((offer) => (
          <article key={offer.id} className={`rounded-xl border p-3 shadow-sm ${selected.has(offer.id) ? 'border-cyan-300 bg-cyan-50/60' : 'border-[var(--ui-border)] bg-white'}`}>
            <div className="mb-2 flex items-start gap-2">
              <input
                type="checkbox"
                checked={selected.has(offer.id)}
                onChange={() => toggleSelect(offer.id)}
                disabled={candidatureStatuts[offer.id] === 'envoyée'}
                className="mt-1 rounded border-gray-300 disabled:opacity-40"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-[var(--ui-text)]">{offer.title}</p>
                <p className="truncate text-xs text-[var(--ui-muted)]">{offer.company}</p>
              </div>
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <ScoreBadge score={offer.score} />
              <StatusBadge status={offer.status} />
              <span className="text-xs text-[var(--ui-muted)]">{offer.location ?? 'Lieu non précisé'}</span>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setFicheOffer(offer)} className="rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)]">Fiche</button>
              <button
                onClick={() => quickGenerate(offer)}
                disabled={generatingId === offer.id}
                className="rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)] disabled:opacity-60"
              >
                {generatingId === offer.id ? 'LM…' : 'LM IA'}
              </button>
              <button
                onClick={() => setApplyOffer(offer)}
                disabled={candidatureStatuts[offer.id] === 'envoyée'}
                className="rounded-md bg-[var(--ui-brand)] px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {candidatureStatuts[offer.id] === 'envoyée' ? 'Déjà postulé' : 'Postuler'}
              </button>
              <button onClick={() => setFormOffer(offer)} className="rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)]">Modifier</button>
              <button
                onClick={() => handleDelete(offer.id)}
                disabled={deletingId === offer.id}
                className="rounded-md border border-red-200 px-2 py-1 text-xs text-red-500 hover:bg-red-50 disabled:opacity-50"
              >
                Suppr.
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="hidden md:block">
        <p className="mb-1 text-[11px] text-[var(--ui-muted)] xl:hidden">Fais défiler horizontalement pour voir toutes les colonnes.</p>
        <div className="overflow-x-auto rounded-xl border border-[var(--ui-border)] shadow-sm">
        <table className="min-w-[1080px] divide-y divide-[var(--ui-border)] text-sm 2xl:min-w-full">
          <thead className="bg-[var(--ui-bg-soft)]">
            <tr>
              <th className="px-3 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectableOffers.length > 0 && selected.size === selectableOffers.length}
                  onChange={toggleAll}
                  className="rounded border-gray-300"
                />
              </th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Titre</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Employeur</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Lieu</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Score</th>
              <th className="hidden px-3 py-3 text-left font-medium text-[var(--ui-muted)] xl:table-cell">Date limite</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Statut</th>
              <th className="hidden px-3 py-3 text-left font-medium text-[var(--ui-muted)] 2xl:table-cell">Source</th>
              <th className="hidden px-3 py-3 text-left font-medium text-[var(--ui-muted)] xl:table-cell">Fiche</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--ui-border)] bg-white">
            {loading && (
              <tr>
                <td colSpan={10} className="px-3 py-8 text-center text-[var(--ui-muted)]">Chargement…</td>
              </tr>
            )}
            {!loading && offers.length === 0 && (
              <tr>
                <td colSpan={10} className="px-3 py-8 text-center text-[var(--ui-muted)]">Aucune offre trouvée</td>
              </tr>
            )}
            {!loading && offers.map((offer) => (
              <tr key={offer.id} className={`transition-colors hover:bg-[var(--ui-bg-soft)] ${selected.has(offer.id) ? 'bg-cyan-50/60' : ''}`}>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(offer.id)}
                    onChange={() => toggleSelect(offer.id)}
                    disabled={candidatureStatuts[offer.id] === 'envoyée'}
                    className="rounded border-gray-300 disabled:opacity-40"
                  />
                </td>
                <td className="max-w-[220px] px-3 py-2">
                  {offer.url ? (
                    <a href={offer.url} target="_blank" rel="noopener noreferrer" className="block truncate font-medium text-[var(--ui-brand)] hover:underline">
                      {offer.title}
                    </a>
                  ) : (
                    <span className="block truncate font-medium">{offer.title}</span>
                  )}
                </td>
                <td className="max-w-[160px] truncate px-3 py-2 text-[var(--ui-text)]">{offer.company}</td>
                <td className="max-w-[140px] truncate px-3 py-2 text-[var(--ui-muted)]">{offer.location ?? '—'}</td>
                <td className="px-3 py-2"><ScoreBadge score={offer.score} /></td>
                <td className="hidden whitespace-nowrap px-3 py-2 text-[var(--ui-muted)] xl:table-cell">{offer.date_limite ?? '—'}</td>
                <td className="px-3 py-2"><StatusBadge status={offer.status} /></td>
                <td className="hidden max-w-[130px] truncate px-3 py-2 text-xs text-[var(--ui-muted)] 2xl:table-cell">
                  {offer.source_name ?? '—'}
                </td>
                <td className="hidden px-3 py-2 xl:table-cell">
                  <button
                    onClick={() => setFicheOffer(offer)}
                    title="Voir la fiche"
                    className="rounded p-1 text-[var(--ui-brand)] transition-colors hover:bg-cyan-50"
                  >
                    <FileText size={14} />
                  </button>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    {offer.contact_email ? (
                      <a
                        href={`mailto:${offer.contact_email}`}
                        title={offer.contact_email}
                        className="rounded p-1 text-cyan-600 transition-colors hover:bg-cyan-50 hover:text-cyan-700"
                      >
                        <Mail size={14} />
                      </a>
                    ) : (
                      <span className="p-1 text-gray-200"><Mail size={14} /></span>
                    )}
                    <button
                      onClick={() => quickGenerate(offer)}
                      disabled={generatingId === offer.id}
                      title="Générer la lettre de motivation"
                      className="rounded p-1 text-[var(--ui-muted)] transition-colors hover:bg-[var(--ui-bg-soft)] hover:text-[var(--ui-brand)] disabled:opacity-50"
                    >
                      {generatingId === offer.id
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Wand2 size={14} />}
                    </button>
                    <div className="flex flex-col items-start gap-0.5">
                      <button
                        onClick={() => setApplyOffer(offer)}
                        disabled={candidatureStatuts[offer.id] === 'envoyée'}
                        title={candidatureStatuts[offer.id] === 'envoyée' ? 'Déjà postulé' : 'Postuler'}
                        className="rounded p-1 text-[var(--ui-muted)] transition-colors hover:bg-[var(--ui-bg-soft)] hover:text-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[var(--ui-muted)]"
                      >
                        <Send size={14} />
                      </button>
                      {candidatureStatuts[offer.id] && (
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${
                          candidatureStatuts[offer.id] === 'envoyée'
                            ? 'bg-emerald-100 text-emerald-700'
                            : candidatureStatuts[offer.id] === 'brouillon'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}>
                          {candidatureStatuts[offer.id]}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => setFormOffer(offer)}
                      title="Modifier"
                      className="rounded p-1 text-[var(--ui-muted)] transition-colors hover:bg-[var(--ui-bg-soft)] hover:text-amber-600"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(offer.id)}
                      disabled={deletingId === offer.id}
                      title="Supprimer"
                      className="rounded p-1 text-[var(--ui-muted)] transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-full bg-gray-900 px-5 py-3 text-white shadow-xl">
          <span className="text-sm">{selected.size} sélectionnée(s)</span>
          <button
            onClick={batchApply}
            disabled={batchLoading}
            className="rounded-full bg-[var(--ui-brand)] px-4 py-1.5 text-sm font-medium hover:brightness-110 disabled:opacity-60"
          >
            {batchLoading ? 'Envoi…' : 'Postuler'}
          </button>
          <button
            onClick={batchGenerateAndAutoApply}
            disabled={batchAutoLoading}
            className="rounded-full bg-emerald-600 px-4 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-60"
          >
            {batchAutoLoading ? 'Traitement…' : 'LM + Auto'}
          </button>
          <button
            onClick={batchDelete}
            disabled={batchDeleting}
            className="rounded-full bg-red-600 px-4 py-1.5 text-sm font-medium hover:bg-red-500 disabled:opacity-60"
          >
            {batchDeleting ? 'Suppression…' : 'Supprimer'}
          </button>
          <button onClick={() => setSelected(new Set())} className="text-sm text-gray-300 hover:text-white">
            Annuler
          </button>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-gray-900 px-4 py-2.5 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      {formOffer !== undefined && (
        <OfferFormModal
          offer={formOffer}
          onClose={() => setFormOffer(undefined)}
          onSaved={() => setReloadSeq((v) => v + 1)}
        />
      )}

      {ficheOffer && (
        <FicheModal offer={ficheOffer} onClose={() => setFicheOffer(null)} />
      )}

      {applyOffer && (
        <ApplyModal
          offer={applyOffer}
          onClose={() => setApplyOffer(null)}
          onSuccess={() => {
            onCandidatureCreated()
            setReloadSeq((v) => v + 1)
          }}
        />
      )}
    </div>
  )
}
