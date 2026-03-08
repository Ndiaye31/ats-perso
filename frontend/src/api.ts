import type {
  Candidature,
  CandidatureStatusItem,
  CandidatureWithOffer,
  BulkOperationResponse,
  Offer,
  OfferCreate,
  OfferUpdate,
  OffersTableResponse,
} from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const hasBody = init?.body != null
  const headers = hasBody
    ? { 'Content-Type': 'application/json', ...init?.headers }
    : init?.headers
  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export function getOffers(minScore = 0): Promise<Offer[]> {
  const qs = minScore > 0 ? `?min_score=${minScore}` : ''
  return request<Offer[]>(`/offers${qs}`)
}

export function getOffersTable(params: {
  minScore?: number
  status?: string
  source?: string
  mode?: string
  locationQ?: string
  limit?: number
  offset?: number
  signal?: AbortSignal
}): Promise<OffersTableResponse> {
  const query = new URLSearchParams()
  if (params.minScore && params.minScore > 0) query.set('min_score', String(params.minScore))
  if (params.status && params.status !== 'all') query.set('status', params.status)
  if (params.source && params.source !== 'all') query.set('source', params.source)
  if (params.mode && params.mode !== 'all') query.set('mode', params.mode)
  if (params.locationQ && params.locationQ.trim()) query.set('location_q', params.locationQ.trim())
  query.set('limit', String(params.limit ?? 100))
  query.set('offset', String(params.offset ?? 0))
  return request<OffersTableResponse>(`/offers/table?${query.toString()}`, {
    signal: params.signal,
  })
}

export function getOfferDetail(offerId: string, signal?: AbortSignal): Promise<Offer> {
  return request<Offer>(`/offers/${offerId}`, { signal })
}

export interface OfferDetectResult {
  title: string | null
  company: string | null
  location: string | null
  description: string | null
  date_limite: string | null
  contact_email: string | null
  candidature_url: string | null
}

export function detectOfferFromUrl(url: string): Promise<OfferDetectResult> {
  return request<OfferDetectResult>('/offers/detect', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

export function createOffer(data: OfferCreate): Promise<Offer> {
  return request<Offer>('/offers', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateOffer(id: string, data: OfferUpdate): Promise<Offer> {
  return request<Offer>(`/offers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteOffer(id: string): Promise<void> {
  return request<void>(`/offers/${id}`, { method: 'DELETE' })
}

export function getCandidatures(): Promise<CandidatureWithOffer[]> {
  return request<CandidatureWithOffer[]>('/candidatures')
}

export function getCandidatureStatusMap(signal?: AbortSignal): Promise<CandidatureStatusItem[]> {
  return request<CandidatureStatusItem[]>('/candidatures/status-map', { signal })
}

export function getCandidatureByOffer(offerId: string, signal?: AbortSignal): Promise<Candidature | null> {
  return request<Candidature | null>(`/candidatures/offer/${offerId}`, { signal })
}

export function createCandidature(
  offerId: string,
  emailContact?: string,
): Promise<Candidature> {
  return request<Candidature>('/candidatures', {
    method: 'POST',
    body: JSON.stringify({ offer_id: offerId, email_contact: emailContact ?? null }),
  })
}

export function updateCandidature(
  id: string,
  patch: { statut?: string; lm_texte?: string; date_envoi?: string },
): Promise<Candidature> {
  return request<Candidature>(`/candidatures/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function deleteCandidature(id: string): Promise<void> {
  return request<void>(`/candidatures/${id}`, { method: 'DELETE' })
}

export function generateLM(candidatureId: string): Promise<{ lm_texte: string }> {
  return request(`/candidatures/${candidatureId}/generate-lm`, { method: 'POST' })
}

export function downloadLmPdf(candidatureId: string): void {
  window.open(`${BASE}/candidatures/${candidatureId}/download-lm`, '_blank')
}

export function autoApply(
  candidatureId: string,
  dryRun = false,
): Promise<{ success: boolean; message: string; screenshot_path?: string }> {
  return request(`/candidatures/${candidatureId}/auto-apply?dry_run=${dryRun}`, { method: 'POST' })
}

export function sendEmail(
  candidatureId: string,
): Promise<{ success: boolean; message: string }> {
  return request(`/candidatures/${candidatureId}/send-email`, { method: 'POST' })
}

export function bulkGenerateLM(
  candidatureIds: string[],
): Promise<BulkOperationResponse> {
  return request('/candidatures/bulk-generate-lm', {
    method: 'POST',
    body: JSON.stringify({ candidature_ids: candidatureIds }),
  })
}

export function bulkAutoApply(
  candidatureIds: string[],
  dryRun = false,
  maxConcurrency = 2,
): Promise<BulkOperationResponse> {
  return request('/candidatures/bulk-auto-apply', {
    method: 'POST',
    body: JSON.stringify({
      candidature_ids: candidatureIds,
      dry_run: dryRun,
      max_concurrency: maxConcurrency,
    }),
  })
}

export function bulkGenerateLMAndAutoApply(
  candidatureIds: string[],
  dryRun = false,
  maxConcurrency = 2,
): Promise<BulkOperationResponse> {
  return request('/candidatures/bulk-generate-lm-and-auto-apply', {
    method: 'POST',
    body: JSON.stringify({
      candidature_ids: candidatureIds,
      dry_run: dryRun,
      max_concurrency: maxConcurrency,
    }),
  })
}

export function scrapeAll(): Promise<Record<string, { inserted: number; skipped: number }>> {
  return request('/offres/scrape', { method: 'POST' })
}

export function rescoreAll(): Promise<{ scored: number }> {
  return request('/offres/score', { method: 'POST' })
}
