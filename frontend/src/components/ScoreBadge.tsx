interface Props {
  score: number | null
}

export function ScoreBadge({ score }: Props) {
  if (score === null) {
    return <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-500 ring-1 ring-gray-200">—</span>
  }

  let cls = ''
  if (score >= 80) cls = 'bg-emerald-100 text-emerald-800 ring-emerald-200'
  else if (score >= 60) cls = 'bg-cyan-100 text-cyan-800 ring-cyan-200'
  else if (score >= 40) cls = 'bg-amber-100 text-amber-800 ring-amber-200'
  else cls = 'bg-gray-100 text-gray-600 ring-gray-200'

  return (
    <span className={`inline-flex min-w-12 items-center justify-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${cls}`}>
      {score}/100
    </span>
  )
}
