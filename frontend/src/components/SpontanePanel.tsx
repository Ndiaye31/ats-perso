import { useState, useCallback } from 'react'
import { RefreshCw, Send, Wand2 } from 'lucide-react'
import { spontaneScrapeFT, spontaneFindEmails, spontaneSend, spontaneGetContacts } from '../api'
import type { SpontaneContact } from '../api'
import { SpontaneContactModal } from './SpontaneContactModal'

type StepStatus = 'idle' | 'loading' | 'done' | 'error'

interface StepResult {
  label: string
  value: string
}

interface StepState {
  status: StepStatus
  results: StepResult[]
  error: string | null
}

const initial: StepState = { status: 'idle', results: [], error: null }

const PROFIL_LABELS: Record<string, string> = {
  data: 'Data Analyste',
  powerbi: 'Consultant Power BI',
  sharepoint: 'SharePoint',
}

export function SpontanePanel() {
  const [step1, setStep1] = useState<StepState>(initial)
  const [step2, setStep2] = useState<StepState>(initial)
  const [step3, setStep3] = useState<StepState>(initial)

  const [contacts, setContacts] = useState<SpontaneContact[]>([])
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [selectedContact, setSelectedContact] = useState<SpontaneContact | null>(null)

  const loadContacts = useCallback(async () => {
    setLoadingContacts(true)
    try {
      const data = await spontaneGetContacts()
      setContacts(data)
    } catch {
      setContacts([])
    } finally {
      setLoadingContacts(false)
    }
  }, [])

  async function handleScrapeFT() {
    setStep1({ status: 'loading', results: [], error: null })
    try {
      const r = await spontaneScrapeFT()
      setStep1({
        status: 'done',
        results: [{ label: 'Entreprises trouvées', value: String(r.entreprises) }],
        error: null,
      })
    } catch (e) {
      setStep1({ status: 'error', results: [], error: e instanceof Error ? e.message : String(e) })
    }
  }

  async function handleFindEmails() {
    setStep2({ status: 'loading', results: [], error: null })
    try {
      const r = await spontaneFindEmails()
      setStep2({
        status: 'done',
        results: [
          { label: 'Emails trouvés', value: String(r.trouves) },
          { label: 'Ignorés', value: String(r.ignores) },
        ],
        error: null,
      })
      await loadContacts()
    } catch (e) {
      setStep2({ status: 'error', results: [], error: e instanceof Error ? e.message : String(e) })
    }
  }

  async function handleSendAll() {
    setStep3({ status: 'loading', results: [], error: null })
    try {
      const r = await spontaneSend()
      setStep3({
        status: 'done',
        results: [
          { label: 'Envoyés', value: String(r.envoyes) },
          { label: 'Ignorés', value: String(r.ignores) },
          { label: 'Erreurs', value: String(r.erreurs) },
        ],
        error: null,
      })
      await loadContacts()
    } catch (e) {
      setStep3({ status: 'error', results: [], error: e instanceof Error ? e.message : String(e) })
    }
  }

  function handleContactSent() {
    loadContacts()
  }

  return (
    <div className="space-y-6">
      {/* Pipeline */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-[var(--ui-text)]">Pipeline candidatures spontanées</p>
        <Step
          number={1}
          title="Scraper France Travail"
          description="Récupère les offres data / Power BI / SharePoint via l'API officielle."
          state={step1}
          onRun={handleScrapeFT}
          buttonLabel="Lancer le scraping"
        />
        <Step
          number={2}
          title="Trouver les emails RH"
          description="Cherche les contacts RH de chaque entreprise via Hunter.io."
          state={step2}
          onRun={handleFindEmails}
          buttonLabel="Chercher les emails"
          disabled={step1.status !== 'done'}
          disabledReason="Lancez d'abord l'étape 1"
        />
        <Step
          number={3}
          title="Envoyer à tous"
          description="Envoie un email à tous les contacts non encore contactés."
          state={step3}
          onRun={handleSendAll}
          buttonLabel="Envoyer à tous"
          disabled={step2.status !== 'done' && contacts.length === 0}
          disabledReason="Lancez d'abord l'étape 2"
        />
      </div>

      {/* Contacts table */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium text-[var(--ui-text)]">
            Contacts ({contacts.length})
          </p>
          <button
            onClick={loadContacts}
            disabled={loadingContacts}
            className="flex items-center gap-1.5 rounded-md border border-[var(--ui-border)] px-2.5 py-1 text-xs text-[var(--ui-muted)] hover:bg-[var(--ui-bg-soft)] disabled:opacity-50"
          >
            <RefreshCw size={11} className={loadingContacts ? 'animate-spin' : ''} />
            Rafraîchir
          </button>
        </div>

        {contacts.length === 0 ? (
          <div className="rounded-xl border border-[var(--ui-border)] bg-white p-8 text-center text-sm text-[var(--ui-muted)]">
            Aucun contact — lancez les étapes 1 et 2 pour en générer.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-[var(--ui-border)] shadow-sm">
            <table className="min-w-full divide-y divide-[var(--ui-border)] text-sm">
              <thead className="bg-[var(--ui-bg-soft)]">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Contact</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Email</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Entreprise</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Profil</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Lieu</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Statut</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-[var(--ui-muted)]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--ui-border)] bg-white">
                {contacts.map((c) => (
                  <tr key={c.email} className="transition-colors hover:bg-[var(--ui-bg-soft)]">
                    <td className="px-3 py-2 font-medium text-[var(--ui-text)]">
                      {c.prenom} {c.nom}
                    </td>
                    <td className="max-w-[180px] truncate px-3 py-2 text-[var(--ui-muted)]">
                      <a href={`mailto:${c.email}`} className="hover:text-[var(--ui-brand)] hover:underline">
                        {c.email}
                      </a>
                    </td>
                    <td className="max-w-[150px] truncate px-3 py-2 text-[var(--ui-text)]">{c.entreprise}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-[var(--ui-bg-soft)] px-2 py-0.5 text-xs text-[var(--ui-muted)]">
                        {PROFIL_LABELS[c.profil] ?? c.profil}
                      </span>
                    </td>
                    <td className="max-w-[120px] truncate px-3 py-2 text-xs text-[var(--ui-muted)]">{c.lieu || '—'}</td>
                    <td className="px-3 py-2">
                      {c.envoye ? (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          Envoyé
                        </span>
                      ) : (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                          En attente
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => setSelectedContact(c)}
                        title="Générer LM et envoyer"
                        className="flex items-center gap-1 rounded-md border border-[var(--ui-border)] px-2 py-1 text-xs text-[var(--ui-muted)] transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                      >
                        <Wand2 size={11} />
                        <Send size={11} />
                        LM + Envoyer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedContact && (
        <SpontaneContactModal
          contact={selectedContact}
          onClose={() => setSelectedContact(null)}
          onSent={handleContactSent}
        />
      )}
    </div>
  )
}

// ─── Step component ─────────────────────────────────────────────

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
    <div
      className={`rounded-xl border p-4 transition-colors ${
        state.status === 'done'
          ? 'border-green-200 bg-green-50'
          : state.status === 'error'
          ? 'border-red-200 bg-red-50'
          : 'border-[var(--ui-border)] bg-white'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span
            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
              state.status === 'done'
                ? 'bg-green-500 text-white'
                : state.status === 'error'
                ? 'bg-red-500 text-white'
                : 'bg-[var(--ui-brand)] text-white'
            }`}
          >
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
