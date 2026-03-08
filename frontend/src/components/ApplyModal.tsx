import { useState, useEffect } from 'react'
import { X, Wand2, Mail, ExternalLink, Loader2, Eye, Pencil, Paperclip, Bot, Send, Download } from 'lucide-react'
import type { OfferTableItem } from '../types'
import { createCandidature, getCandidatureByOffer, updateCandidature, generateLM, autoApply, sendEmail, downloadLmPdf } from '../api'
import { ScoreBadge } from './ScoreBadge'
import { getApplyModeLabel, getOfferPlatformName } from '../modeLabels'

interface Props {
  offer: OfferTableItem
  onClose: () => void
  onSuccess: () => void
}

type Mode = 'email' | 'plateforme' | 'portail_tiers' | 'inconnu'

function getPortalHost(candidatureUrl?: string | null): string {
  if (!candidatureUrl) return ''
  try {
    return new URL(candidatureUrl).hostname
  } catch {
    return candidatureUrl
  }
}

function ModeBadge({ mode, offer }: { mode: Mode; offer: OfferTableItem }) {
  const platformName = getOfferPlatformName(offer)
  const styles: Record<Mode, string> = {
    email: 'bg-blue-100 text-blue-700',
    plateforme: 'bg-purple-100 text-purple-700',
    portail_tiers: 'bg-orange-100 text-orange-700',
    inconnu: 'bg-slate-100 text-slate-700',
  }
  const labels: Record<Mode, string> = {
    email: '✉ Candidature par email',
    plateforme: `🌐 ${getApplyModeLabel(offer)}`,
    portail_tiers: `🔗 ${getApplyModeLabel(offer)}${offer.candidature_url ? ` — ${getPortalHost(offer.candidature_url)}` : ''}`,
    inconnu: `🌐 ${platformName ?? 'Plateforme'}`,
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${styles[mode]}`}>
      {labels[mode]}
    </span>
  )
}

function detectMode(offer: OfferTableItem): Mode {
  if (offer.candidature_url) return 'portail_tiers'
  if (offer.contact_email) return 'email'
  if (offer.url) return 'plateforme'
  return 'inconnu'
}

export function ApplyModal({ offer, onClose, onSuccess }: Props) {
  const mode = detectMode(offer)
  const [view, setView] = useState<'edit' | 'preview'>('edit')
  const [email, setEmail] = useState(offer.contact_email ?? '')
  const [lm, setLm] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [sending, setSending] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [candidatureId, setCandidatureId] = useState<string | null>(null)

  const isAutoSupported =
    offer.url != null &&
    !offer.candidature_url &&
    (
      offer.url.includes('emploi-territorial.fr') ||
      offer.url.includes('emploi.fhf.fr') ||
      offer.url.includes('hellowork.com')
    )

  const subject = `Candidature — ${offer.title}`

  // Charge la candidature existante à l'ouverture
  useEffect(() => {
    const controller = new AbortController()
    getCandidatureByOffer(offer.id, controller.signal).then((existing) => {
      if (existing) {
        setCandidatureId(existing.id)
        if (existing.lm_texte) setLm(existing.lm_texte)
        if (existing.email_contact) setEmail(existing.email_contact)
      }
    }).catch(() => {})
    return () => controller.abort()
  }, [offer.id])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  async function ensureCandidature(): Promise<string> {
    if (candidatureId) return candidatureId
    const cand = await createCandidature(offer.id, email || undefined)
    setCandidatureId(cand.id)
    return cand.id
  }

  async function handleGenerate() {
    setGenerating(true)
    try {
      const id = await ensureCandidature()
      const res = await generateLM(id)
      setLm(res.lm_texte)
    } catch (err) {
      showToast(`Erreur génération : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setGenerating(false)
    }
  }

  async function handleSave(statut: string) {
    setLoading(true)
    try {
      const id = await ensureCandidature()
      await updateCandidature(id, {
        statut,
        lm_texte: lm || undefined,
        date_envoi: statut === 'envoyée' ? new Date().toISOString().slice(0, 10) : undefined,
      })
      showToast(statut === 'envoyée' ? 'Candidature marquée comme envoyée !' : 'Brouillon enregistré')
      setTimeout(() => { onSuccess(); onClose() }, 1200)
    } catch (err) {
      showToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
      setLoading(false)
    }
  }

  function handleEmailClient() {
    const gmailUrl = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(email)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(lm || '')}`
    window.open(gmailUrl, '_blank')
    handleSave('envoyée')
  }

  async function handleSendEmail() {
    setSending(true)
    try {
      const id = await ensureCandidature()
      // Sauvegarde la LM avant l'envoi
      if (lm) await updateCandidature(id, { lm_texte: lm })
      const res = await sendEmail(id)
      showToast(res.message)
      setTimeout(() => { onSuccess(); onClose() }, 1500)
    } catch (err) {
      showToast(`Erreur envoi : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setSending(false)
    }
  }

  function handlePlatform() {
    if (offer.url) window.open(offer.url, '_blank')
    handleSave('envoyée')
  }

  async function handleAutoApply(dryRun: boolean) {
    setApplying(true)
    try {
      const id = await ensureCandidature()
      const res = await autoApply(id, dryRun)
      if (res.success) {
        showToast(dryRun ? `Dry-run OK — ${res.message}` : 'Candidature envoyée automatiquement !')
        if (!dryRun) setTimeout(() => { onSuccess(); onClose() }, 1500)
      } else {
        showToast(`Échec : ${res.message}`)
      }
    } catch (err) {
      showToast(`Erreur : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setApplying(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 px-6 py-4 border-b border-gray-200">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900">{offer.title}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{offer.company}{offer.location ? ` · ${offer.location}` : ''}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 text-gray-400 flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {/* Tabs Rédaction / Prévisualisation */}
        <div className="flex border-b border-gray-200 px-6">
          <button
            onClick={() => setView('edit')}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px ${
              view === 'edit'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Pencil size={12} /> Rédaction
          </button>
          <button
            onClick={() => setView('preview')}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px ${
              view === 'preview'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Eye size={12} /> Prévisualisation
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">

          {view === 'edit' && (
            <>
              {/* Mode + score */}
              <div className="flex items-center gap-3 flex-wrap">
                <ScoreBadge score={offer.score} />
                <ModeBadge mode={mode} offer={offer} />
                {offer.date_limite && (
                  <span className="text-xs text-gray-500">Limite : {offer.date_limite}</span>
                )}
              </div>

              {/* Email (mode email seulement) */}
              {mode === 'email' && (
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Email de contact</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="recrutement@example.fr"
                    className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}

              {/* Rappel CV */}
              {mode === 'email' && (
                <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800">
                  <Paperclip size={13} className="mt-0.5 shrink-0" />
                  <span>Pensez à joindre votre CV à l'email — <span className="font-mono">config/cv_amadou_mactar_ndiaye.pdf</span></span>
                </div>
              )}

              {/* Lettre de motivation */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700">Lettre de motivation</label>
                  <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-700 text-xs font-medium hover:bg-indigo-100 disabled:opacity-60 transition-colors"
                  >
                    {generating
                      ? <><Loader2 size={12} className="animate-spin" /> Génération…</>
                      : <><Wand2 size={12} /> Générer avec Claude</>
                    }
                  </button>
                </div>
                <textarea
                  value={lm}
                  onChange={(e) => setLm(e.target.value)}
                  rows={10}
                  placeholder="Cliquez sur « Générer avec Claude » ou rédigez votre lettre ici…"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y font-mono"
                />
              </div>
            </>
          )}

          {view === 'preview' && (
            <div className="border border-gray-200 rounded-lg overflow-hidden text-sm">
              {/* En-têtes email */}
              <div className="bg-gray-50 border-b border-gray-200 px-4 py-3 space-y-1.5">
                {mode === 'email' && (
                  <div className="flex gap-2">
                    <span className="text-xs font-medium text-gray-500 w-12 shrink-0 pt-0.5">À :</span>
                    <span className="text-gray-800">{email || <span className="text-red-400 italic">Aucun email renseigné</span>}</span>
                  </div>
                )}
                <div className="flex gap-2">
                  <span className="text-xs font-medium text-gray-500 w-12 shrink-0 pt-0.5">Objet :</span>
                  <span className="text-gray-800 font-medium">{subject}</span>
                </div>
              </div>
              {/* Corps */}
              <div className="px-4 py-4 bg-white">
                {lm
                  ? <p className="whitespace-pre-wrap text-gray-800 leading-relaxed">{lm}</p>
                  : <p className="text-gray-400 italic">Aucune lettre rédigée. Retournez en mode Rédaction pour en générer une.</p>
                }
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between gap-3 px-6 py-3 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            onClick={() => handleSave('brouillon')}
            disabled={loading}
            className="px-3 py-1.5 rounded-md border border-gray-300 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-60 transition-colors"
          >
            Enregistrer brouillon
          </button>

          <div className="flex gap-2">
            {isAutoSupported && (
              <>
                {email && (
                  <button
                    onClick={handleSendEmail}
                    disabled={sending || !email}
                    title="Envoyer par email (si le formulaire en ligne n'est pas disponible)"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-blue-300 text-blue-700 text-sm font-medium hover:bg-blue-50 disabled:opacity-60 transition-colors"
                  >
                    {sending ? <Loader2 size={14} className="animate-spin" /> : <Mail size={14} />}
                    Email
                  </button>
                )}
                <button
                  onClick={() => handleAutoApply(true)}
                  disabled={applying}
                  title="Dry-run : screenshot sans soumettre"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-indigo-300 text-indigo-700 text-sm font-medium hover:bg-indigo-50 disabled:opacity-60 transition-colors"
                >
                  {applying ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
                  Test
                </button>
                <button
                  onClick={() => handleAutoApply(false)}
                  disabled={applying}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
                >
                  {applying ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
                  Postuler automatiquement
                </button>
              </>
            )}
            {mode === 'email' && (
              <>
                <button
                  onClick={handleEmailClient}
                  disabled={loading || !email}
                  title="Ouvre votre client mail avec la LM pré-remplie"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-blue-300 text-blue-700 text-sm font-medium hover:bg-blue-50 disabled:opacity-60 transition-colors"
                >
                  <Mail size={14} />
                  Client mail
                </button>
                <button
                  onClick={handleSendEmail}
                  disabled={sending || !email}
                  title="Envoie directement depuis Gmail via SMTP"
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
                >
                  {sending
                    ? <><Loader2 size={14} className="animate-spin" /> Envoi…</>
                    : <><Send size={14} /> Envoyer par email</>
                  }
                </button>
              </>
            )}
            {mode === 'plateforme' && !isAutoSupported && (
              <>
                {email && (
                  <button
                    onClick={handleEmailClient}
                    disabled={loading}
                    title="Fallback : envoyer par email"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-blue-300 text-blue-700 text-sm font-medium hover:bg-blue-50 disabled:opacity-60 transition-colors"
                  >
                    <Mail size={14} />
                    Client mail
                  </button>
                )}
                <button
                  onClick={handlePlatform}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-purple-600 text-white text-sm font-medium hover:bg-purple-700 disabled:opacity-60 transition-colors"
                >
                  <ExternalLink size={14} />
                  Aller sur la plateforme
                </button>
              </>
            )}
            {mode === 'portail_tiers' && (
              <>
                {candidatureId && lm && (
                  <button
                    onClick={() => downloadLmPdf(candidatureId)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-orange-300 text-orange-700 text-sm font-medium hover:bg-orange-50 transition-colors"
                  >
                    <Download size={14} />
                    Télécharger LM
                  </button>
                )}
                <button
                  onClick={() => window.open(offer.candidature_url!, '_blank')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-orange-300 text-orange-700 text-sm font-medium hover:bg-orange-50 transition-colors"
                >
                  <ExternalLink size={14} />
                  Aller sur le portail
                </button>
                <button
                  onClick={() => handleSave('envoyée')}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-orange-500 text-white text-sm font-medium hover:bg-orange-600 disabled:opacity-60 transition-colors"
                >
                  <Send size={14} />
                  Confirmer envoyée
                </button>
              </>
            )}
          </div>
        </div>

        {toast && (
          <div className="fixed bottom-6 right-6 z-50 bg-gray-900 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg">
            {toast}
          </div>
        )}
      </div>
    </div>
  )
}
