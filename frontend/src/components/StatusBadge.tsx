const STATUS_STYLES: Record<string, string> = {
  new: 'bg-slate-100 text-slate-700 ring-1 ring-slate-200',
  applied: 'bg-cyan-100 text-cyan-800 ring-1 ring-cyan-200',
  interview: 'bg-violet-100 text-violet-800 ring-1 ring-violet-200',
  rejected: 'bg-rose-100 text-rose-700 ring-1 ring-rose-200',
  accepted: 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200',
  brouillon: 'bg-amber-100 text-amber-800 ring-1 ring-amber-200',
  envoyée: 'bg-cyan-100 text-cyan-800 ring-1 ring-cyan-200',
  annulée: 'bg-rose-100 text-rose-700 ring-1 ring-rose-200',
}

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  applied: 'Postulé',
  interview: 'Entretien',
  rejected: 'Refusé',
  accepted: 'Accepté',
  brouillon: 'Brouillon',
  envoyée: 'Envoyée',
  annulée: 'Annulée',
}

interface Props {
  status: string
}

export function StatusBadge({ status }: Props) {
  const cls = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600'
  const label = STATUS_LABELS[status] ?? status
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>
      {label}
    </span>
  )
}
