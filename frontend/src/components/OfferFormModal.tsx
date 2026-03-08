import { useState } from 'react'
import { X, Loader2, Search } from 'lucide-react'
import type { OfferTableItem } from '../types'
import { createOffer, updateOffer, detectOfferFromUrl } from '../api'

interface Props {
  offer?: OfferTableItem | null
  onClose: () => void
  onSaved: () => void
}

export function OfferFormModal({ offer, onClose, onSaved }: Props) {
  const isEdit = !!offer
  const [title, setTitle] = useState(offer?.title ?? '')
  const [company, setCompany] = useState(offer?.company ?? '')
  const [location, setLocation] = useState(offer?.location ?? '')
  const [url, setUrl] = useState(offer?.url ?? '')
  const [dateLimite, setDateLimite] = useState(offer?.date_limite ?? '')
  const [contactEmail, setContactEmail] = useState(offer?.contact_email ?? '')
  const [candidatureUrl, setCandidatureUrl] = useState(offer?.candidature_url ?? '')
  const [status, setStatus] = useState(offer?.status ?? 'new')
  const [saving, setSaving] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDetect() {
    const trimmed = url.trim()
    if (!trimmed) return
    setDetecting(true)
    setError(null)
    try {
      const result = await detectOfferFromUrl(trimmed)
      if (result.title && !title) setTitle(result.title)
      if (result.company && !company) setCompany(result.company)
      if (result.location && !location) setLocation(result.location)
      if (result.date_limite && !dateLimite) setDateLimite(result.date_limite)
      if (result.contact_email && !contactEmail) setContactEmail(result.contact_email)
      if (result.candidature_url && !candidatureUrl) setCandidatureUrl(result.candidature_url)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setDetecting(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || !company.trim()) return
    setSaving(true)
    setError(null)
    try {
      const data = {
        title: title.trim(),
        company: company.trim(),
        location: location.trim() || null,
        url: url.trim() || null,
        date_limite: dateLimite.trim() || null,
        contact_email: contactEmail.trim() || null,
        candidature_url: candidatureUrl.trim() || null,
        status,
      }
      if (isEdit) {
        await updateOffer(offer!.id, data)
      } else {
        await createOffer(data)
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const inputClass =
    'w-full rounded-md border border-[var(--ui-border)] bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-300'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="relative mx-4 w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button onClick={onClose} className="absolute right-4 top-4 text-gray-400 hover:text-gray-600">
          <X size={18} />
        </button>

        <h2 className="mb-4 text-lg font-semibold text-[var(--ui-text)]">
          {isEdit ? 'Modifier l\u2019offre' : 'Ajouter une offre'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-[var(--ui-muted)]">URL de l&apos;offre</label>
            <div className="flex gap-2">
              <input value={url} onChange={(e) => setUrl(e.target.value)} type="url" placeholder="https://..." className={inputClass} />
              <button
                type="button"
                onClick={handleDetect}
                disabled={detecting || !url.trim()}
                title="Détecter les infos depuis l'URL"
                className="flex shrink-0 items-center gap-1.5 rounded-md border border-[var(--ui-border)] px-3 py-2 text-xs font-medium text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)] disabled:opacity-50"
              >
                {detecting ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                Détecter
              </button>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--ui-muted)]">Titre *</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--ui-muted)]">Entreprise *</label>
            <input value={company} onChange={(e) => setCompany(e.target.value)} required className={inputClass} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--ui-muted)]">Localisation</label>
              <input value={location} onChange={(e) => setLocation(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--ui-muted)]">Statut</label>
              <select value={status} onChange={(e) => setStatus(e.target.value)} className={inputClass}>
                <option value="new">new</option>
                <option value="applied">applied</option>
                <option value="rejected">rejected</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--ui-muted)]">Date limite</label>
              <input
                value={dateLimite}
                onChange={(e) => setDateLimite(e.target.value)}
                placeholder="dd/mm/yyyy"
                className={inputClass}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--ui-muted)]">Email contact</label>
              <input
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                type="email"
                className={inputClass}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--ui-muted)]">URL candidature (portail tiers)</label>
            <input
              value={candidatureUrl}
              onChange={(e) => setCandidatureUrl(e.target.value)}
              type="url"
              className={inputClass}
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-[var(--ui-border)] px-4 py-2 text-sm text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)]"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={saving || !title.trim() || !company.trim()}
              className="flex items-center gap-2 rounded-md bg-[var(--ui-brand)] px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-60"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              {isEdit ? 'Enregistrer' : 'Ajouter'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
