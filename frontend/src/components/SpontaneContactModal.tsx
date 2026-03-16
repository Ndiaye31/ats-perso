import { useState } from 'react'
import { X, Wand2, Send, Eye, Pencil, Loader2, Paperclip } from 'lucide-react'
import type { SpontaneContact } from '../api'
import { spontaneGenerateLM, spontaneSendOne } from '../api'

const PROFIL_LABELS: Record<string, string> = {
  data: 'Data Analyste',
  powerbi: 'Consultant Power BI',
  sharepoint: 'Administrateur SharePoint Online',
}

interface Props {
  contact: SpontaneContact
  onClose: () => void
  onSent: () => void
}

export function SpontaneContactModal({ contact, onClose, onSent }: Props) {
  const [view, setView] = useState<'edit' | 'preview'>('edit')
  const [lm, setLm] = useState('')
  const [generating, setGenerating] = useState(false)
  const [sending, setSending] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const titre = PROFIL_LABELS[contact.profil] ?? contact.profil
  const subject = `Candidature spontanée – ${titre}`

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  async function handleGenerate() {
    setGenerating(true)
    try {
      const res = await spontaneGenerateLM({
        prenom: contact.prenom,
        entreprise: contact.entreprise,
        profil: contact.profil,
        lieu: contact.lieu,
      })
      setLm(res.lm_texte)
    } catch (err) {
      showToast(`Erreur génération : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setGenerating(false)
    }
  }

  async function handleSend() {
    if (!lm.trim()) {
      showToast('Rédigez ou générez une lettre avant d\'envoyer')
      return
    }
    setSending(true)
    try {
      const res = await spontaneSendOne({
        prenom: contact.prenom,
        nom: contact.nom,
        email: contact.email,
        entreprise: contact.entreprise,
        profil: contact.profil,
        lm_texte: lm,
      })
      showToast(res.message)
      setTimeout(() => { onSent(); onClose() }, 1500)
    } catch (err) {
      showToast(`Erreur envoi : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setSending(false)
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
            <h2 className="text-base font-semibold text-gray-900">
              {contact.prenom} {contact.nom}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {contact.entreprise}{contact.lieu ? ` · ${contact.lieu}` : ''} — <span className="text-[var(--ui-brand)]">{titre}</span>
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 text-gray-400 flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {/* Tabs */}
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
              <div className="flex items-center gap-3 flex-wrap text-xs text-gray-500">
                <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">
                  ✉ Candidature spontanée par email
                </span>
                {contact.envoye && (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 font-medium">
                    ✓ Déjà envoyé
                  </span>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Email de contact</label>
                <input
                  type="email"
                  value={contact.email}
                  readOnly
                  className="w-full border border-gray-200 rounded-md px-3 py-1.5 text-sm bg-gray-50 text-gray-600"
                />
              </div>

              <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800">
                <Paperclip size={13} className="mt-0.5 shrink-0" />
                <span>Pensez à joindre votre CV — <span className="font-mono">config/cv_amadou_mactar_ndiaye.pdf</span></span>
              </div>

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
              <div className="bg-gray-50 border-b border-gray-200 px-4 py-3 space-y-1.5">
                <div className="flex gap-2">
                  <span className="text-xs font-medium text-gray-500 w-12 shrink-0 pt-0.5">À :</span>
                  <span className="text-gray-800">{contact.email}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-xs font-medium text-gray-500 w-12 shrink-0 pt-0.5">Objet :</span>
                  <span className="text-gray-800 font-medium">{subject}</span>
                </div>
              </div>
              <div className="px-4 py-4 bg-white">
                {lm
                  ? <p className="whitespace-pre-wrap text-gray-800 leading-relaxed">{lm}</p>
                  : <p className="text-gray-400 italic">Aucune lettre rédigée. Revenez en mode Rédaction.</p>
                }
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-3 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            onClick={handleSend}
            disabled={sending || !lm.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {sending
              ? <><Loader2 size={14} className="animate-spin" /> Envoi…</>
              : <><Send size={14} /> Envoyer par email</>
            }
          </button>
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
