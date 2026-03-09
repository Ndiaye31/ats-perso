import type { CandidatureWithOffer, OfferTableItem } from './types'

type ModeValue = CandidatureWithOffer['mode_candidature']

function getHost(url?: string | null): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.toLowerCase()
  } catch {
    return url.toLowerCase()
  }
}

function getPlatformNameFromUrl(url?: string | null): string | null {
  const host = getHost(url)
  if (!host) return null
  if (host.includes('emploi-territorial.fr')) return 'Emploi-Territorial'
  if (host.includes('emploi.fhf.fr') || host.includes('fhf.fr')) return 'FHF'
  return null
}

export function getOfferPlatformName(offer: Pick<OfferTableItem, 'url' | 'candidature_url'>): string | null {
  return getPlatformNameFromUrl(offer.candidature_url) ?? getPlatformNameFromUrl(offer.url)
}

export function getCandidatureModeLabel(candidature: Pick<CandidatureWithOffer, 'mode_candidature' | 'offer_url'>): string {
  if (candidature.mode_candidature === 'email') return 'Email'
  if (candidature.mode_candidature === 'portail_tiers') return 'Portail tiers'
  return getPlatformNameFromUrl(candidature.offer_url) ?? 'Plateforme'
}

export function getModeBadgeTone(candidature: Pick<CandidatureWithOffer, 'mode_candidature' | 'offer_url'>): string {
  if (candidature.mode_candidature === 'email') {
    return 'bg-cyan-100 text-cyan-800 ring-1 ring-cyan-200'
  }
  if (candidature.mode_candidature === 'portail_tiers') {
    return 'bg-orange-100 text-orange-800 ring-1 ring-orange-200'
  }
  const platformName = getPlatformNameFromUrl(candidature.offer_url)
  if (platformName === 'FHF') {
    return 'bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200'
  }
  if (platformName === 'Emploi-Territorial') {
    return 'bg-violet-100 text-violet-800 ring-1 ring-violet-200'
  }
  return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'
}

export function getApplyModeLabel(offer: Pick<OfferTableItem, 'url' | 'candidature_url' | 'contact_email'>): string {
  if (offer.candidature_url) {
    const platformName = getPlatformNameFromUrl(offer.candidature_url)
    return platformName ? `Portail tiers - ${platformName}` : 'Portail tiers'
  }
  if (offer.contact_email) return 'Candidature par email'
  return getPlatformNameFromUrl(offer.url) ?? 'Plateforme'
}
