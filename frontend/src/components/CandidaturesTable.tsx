import { useEffect, useState } from 'react'
import { FileText, X, Download } from 'lucide-react'
import type { CandidatureWithOffer } from '../types'
import { getCandidatures, updateCandidature, deleteCandidature, downloadLmPdf } from '../api'
import { StatusBadge } from './StatusBadge'

interface Props {
  refreshKey: number
}

function ModeBadge({ mode }: { mode: CandidatureWithOffer['mode_candidature'] }) {
  if (mode === 'email') {
    return <span className="inline-flex rounded-full bg-cyan-100 px-2.5 py-1 text-xs font-semibold text-cyan-800 ring-1 ring-cyan-200">Email</span>
  }
  if (mode === 'plateforme') {
    return <span className="inline-flex rounded-full bg-violet-100 px-2.5 py-1 text-xs font-semibold text-violet-800 ring-1 ring-violet-200">Plateforme</span>
  }
  if (mode === 'portail_tiers') {
    return <span className="inline-flex rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-orange-800 ring-1 ring-orange-200">Portail tiers</span>
  }
  return <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600 ring-1 ring-gray-200">Inconnu</span>
}

export function CandidaturesTable({ refreshKey }: Props) {
  const [candidatures, setCandidatures] = useState<CandidatureWithOffer[]>([])
  const [loading, setLoading] = useState(true)
  const [popover, setPopover] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    try {
      setCandidatures(await getCandidatures())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [refreshKey])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  async function cancel(id: string) {
    try {
      await updateCandidature(id, { statut: 'annulée' })
      showToast('Candidature annulée')
      load()
    } catch (err) {
      showToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  async function remove(id: string) {
    if (!confirm('Supprimer définitivement cette candidature ?')) return
    try {
      await deleteCandidature(id)
      showToast('Candidature supprimée')
      load()
    } catch (err) {
      showToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3 md:hidden">
        {loading && (
          <div className="rounded-xl border border-[var(--ui-border)] bg-white p-4 text-sm text-[var(--ui-muted)]">
            Chargement…
          </div>
        )}
        {!loading && candidatures.length === 0 && (
          <div className="rounded-xl border border-[var(--ui-border)] bg-white p-4 text-sm text-[var(--ui-muted)]">
            Aucune candidature
          </div>
        )}
        {!loading && candidatures.map((c) => (
          <article key={c.id} className="rounded-xl border border-[var(--ui-border)] bg-white p-3 shadow-sm">
            <div className="mb-2 min-w-0">
              {c.offer_url ? (
                <a href={c.offer_url} target="_blank" rel="noopener noreferrer" className="block truncate text-sm font-semibold text-[var(--ui-brand)] hover:underline">
                  {c.offer_title}
                </a>
              ) : (
                <p className="truncate text-sm font-semibold text-[var(--ui-text)]">{c.offer_title}</p>
              )}
              <p className="truncate text-xs text-[var(--ui-muted)]">{c.offer_company}</p>
            </div>

            <div className="mb-2 flex flex-wrap items-center gap-2">
              <ModeBadge mode={c.mode_candidature} />
              <StatusBadge status={c.statut} />
              <span className="text-xs text-[var(--ui-muted)]">{c.date_envoi ?? 'Non envoyée'}</span>
            </div>

            <div className="mb-3 text-xs text-[var(--ui-muted)]">
              Contact: {c.email_contact ?? '—'}
            </div>

            <div className="flex items-center gap-2">
              {c.lm_texte ? (
                <button
                  onClick={() => setPopover(popover === c.id ? null : c.id)}
                  className="rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)]"
                  title="Voir LM"
                >
                  Voir LM
                </button>
              ) : (
                <span className="text-xs text-gray-400">LM absente</span>
              )}
              {c.statut !== 'annulée' && (
                <button
                  onClick={() => cancel(c.id)}
                  className="rounded-md border border-rose-200 px-2 py-1 text-xs text-rose-700 hover:bg-rose-50"
                >
                  Annuler
                </button>
              )}
              <button
                onClick={() => remove(c.id)}
                className="rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)]"
              >
                Supprimer
              </button>
            </div>

            {popover === c.id && c.lm_texte && (
              <div className="mt-3 rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-soft)] p-3 text-xs text-[var(--ui-text)] whitespace-pre-wrap">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-semibold">Lettre de motivation</span>
                  <button onClick={() => setPopover(null)} className="text-[var(--ui-muted)]">
                    <X size={12} />
                  </button>
                </div>
                {c.lm_texte}
              </div>
            )}
          </article>
        ))}
      </div>

      <div className="hidden overflow-x-auto rounded-xl border border-[var(--ui-border)] shadow-sm md:block">
        <table className="min-w-full divide-y divide-[var(--ui-border)] text-sm">
          <thead className="bg-[var(--ui-bg-soft)]">
            <tr>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Titre</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Employeur</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Mode</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Statut</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Date envoi</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Email</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">LM</th>
              <th className="px-3 py-3 text-left font-medium text-[var(--ui-muted)]">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--ui-border)] bg-white">
            {loading && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-[var(--ui-muted)]">Chargement…</td>
              </tr>
            )}
            {!loading && candidatures.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-[var(--ui-muted)]">Aucune candidature</td>
              </tr>
            )}
            {!loading && candidatures.map((c) => (
              <tr key={c.id} className="transition-colors hover:bg-[var(--ui-bg-soft)]">
                <td className="max-w-[200px] truncate px-3 py-2 font-medium text-[var(--ui-text)]">
                  {c.offer_url ? (
                    <a href={c.offer_url} target="_blank" rel="noopener noreferrer" className="text-[var(--ui-brand)] hover:underline">
                      {c.offer_title}
                    </a>
                  ) : c.offer_title}
                </td>
                <td className="max-w-[160px] truncate px-3 py-2 text-[var(--ui-muted)]">{c.offer_company}</td>
                <td className="px-3 py-2">
                  <ModeBadge mode={c.mode_candidature} />
                </td>
                <td className="px-3 py-2"><StatusBadge status={c.statut} /></td>
                <td className="whitespace-nowrap px-3 py-2 text-[var(--ui-muted)]">{c.date_envoi ?? '—'}</td>
                <td className="max-w-[180px] truncate px-3 py-2 text-[var(--ui-muted)]">{c.email_contact ?? '—'}</td>
                <td className="px-3 py-2">
                  {c.lm_texte ? (
                    <div className="relative inline-flex items-center gap-1">
                      <button
                        onClick={() => setPopover(popover === c.id ? null : c.id)}
                        className="rounded p-1 text-[var(--ui-muted)] transition-colors hover:bg-[var(--ui-bg-soft)] hover:text-[var(--ui-brand)]"
                        title="Voir LM"
                      >
                        <FileText size={14} />
                      </button>
                      <button
                        onClick={() => downloadLmPdf(c.id)}
                        className="rounded p-1 text-[var(--ui-muted)] transition-colors hover:bg-[var(--ui-bg-soft)] hover:text-orange-600"
                        title="Télécharger LM (PDF)"
                      >
                        <Download size={14} />
                      </button>
                      {popover === c.id && (
                        <div className="absolute left-6 top-0 z-50 max-h-48 w-72 overflow-y-auto whitespace-pre-wrap rounded-lg border border-[var(--ui-border)] bg-white p-3 text-xs text-[var(--ui-text)] shadow-xl">
                          <button
                            onClick={() => setPopover(null)}
                            className="absolute right-2 top-2 text-[var(--ui-muted)] hover:text-[var(--ui-text)]"
                          >
                            <X size={12} />
                          </button>
                          {c.lm_texte}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
                <td className="flex items-center gap-2 px-3 py-2">
                  {c.statut !== 'annulée' && (
                    <button
                      onClick={() => cancel(c.id)}
                      className="text-xs text-rose-600 transition-colors hover:text-rose-700 hover:underline"
                    >
                      Annuler
                    </button>
                  )}
                  <button
                    onClick={() => remove(c.id)}
                    className="text-xs text-[var(--ui-muted)] transition-colors hover:text-rose-700 hover:underline"
                  >
                    Supprimer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-gray-900 px-4 py-2.5 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
