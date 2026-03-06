import { useEffect, useState } from 'react'
import { X, ExternalLink, Mail } from 'lucide-react'
import { getOfferDetail } from '../api'
import type { Offer, OfferTableItem } from '../types'

interface Props {
  offer: OfferTableItem
  onClose: () => void
}

export function FicheModal({ offer, onClose }: Props) {
  const [detail, setDetail] = useState<Offer | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    async function loadDetail() {
      setLoading(true)
      setError(null)
      try {
        const full = await getOfferDetail(offer.id, controller.signal)
        setDetail(full)
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : String(err))
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    loadDetail()
    return () => controller.abort()
  }, [offer.id])

  const description = detail?.description ?? null
  const contactEmail = detail?.contact_email ?? offer.contact_email
  const offerUrl = detail?.url ?? offer.url

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-6 py-4 border-b border-gray-200">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900 leading-snug">{offer.title}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{offer.company}{offer.location ? ` · ${offer.location}` : ''}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 flex-shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-6 py-4 flex-1">
          {loading ? (
            <p className="text-sm text-gray-400 italic">Chargement de la fiche…</p>
          ) : error ? (
            <p className="text-sm text-red-500">Impossible de charger la fiche: {error}</p>
          ) : description ? (
            <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
              {description}
            </pre>
          ) : (
            <p className="text-sm text-gray-400 italic">Aucune description disponible.</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-6 py-3 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          {contactEmail && (
            <a
              href={`mailto:${contactEmail}`}
              className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-indigo-600 transition-colors"
            >
              <Mail size={13} />
              {contactEmail}
            </a>
          )}
          <div className="ml-auto">
            {offerUrl && (
              <a
                href={offerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
              >
                <ExternalLink size={12} />
                Voir l'offre
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
