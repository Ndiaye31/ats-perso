export interface Offer {
  id: string
  title: string
  company: string
  location: string | null
  url: string | null
  description: string | null
  status: string
  applied_at: string | null
  date_limite: string | null
  contact_email: string | null
  candidature_url: string | null
  score: number | null
  score_details: Record<string, unknown> | null
  source_id: string | null
  source_name: string | null
  created_at: string
}

export interface OfferTableItem {
  id: string
  title: string
  company: string
  location: string | null
  url: string | null
  status: string
  date_limite: string | null
  contact_email: string | null
  candidature_url: string | null
  score: number | null
  source_id: string | null
  source_name: string | null
  created_at: string
}

export interface OffersTableResponse {
  items: OfferTableItem[]
  total: number
  limit: number
  offset: number
}

export interface Candidature {
  id: string
  offer_id: string
  statut: string
  mode_candidature: 'email' | 'plateforme' | 'portail_tiers' | 'inconnu'
  lm_texte: string | null
  date_envoi: string | null
  email_contact: string | null
  created_at: string
  updated_at: string
}

export interface CandidatureWithOffer extends Candidature {
  offer_title: string
  offer_company: string
  offer_url: string | null
}

export interface CandidatureStatusItem {
  offer_id: string
  statut: string
}

export interface BulkItemResult {
  candidature_id: string
  success: boolean
  message: string
}

export interface BulkOperationResponse {
  total: number
  success: number
  failed: number
  results: BulkItemResult[]
}
