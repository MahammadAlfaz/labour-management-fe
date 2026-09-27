import { useState } from 'react'
import EmptyState from '../../components/EmptyState'
import { toLocalIsoDate } from '../../lib/date'
import DateRangeFields from './DateRangeFields'
import { weeklySiteExpensesExportUrl } from './api'
import { useWeeklySiteExpensesReport } from './useReports'

/** Sunday-to-Saturday week containing today (see plan: Sat is payday). */
function currentWeekRange(): { start: string; end: string } {
  const d = new Date()
  const start = new Date(d)
  start.setDate(d.getDate() - d.getDay())
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return { start: toLocalIsoDate(start), end: toLocalIsoDate(end) }
}

export default function WeeklySiteExpensesView() {
  const initial = currentWeekRange()
  const [from, setFrom] = useState(initial.start)
  const [to, setTo] = useState(initial.end)

  const { data: report, isLoading } = useWeeklySiteExpensesReport(from, to)

  return (
    <div className="flex flex-col gap-3">
      <DateRangeFields from={from} to={to} onFromChange={setFrom} onToChange={setTo} />

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}

      {report && (
        <>
          <dl className="grid grid-cols-2 gap-2">
            <TotalStat label="Labour salary" value={report.total_labour_cost} />
            <TotalStat label="Petrol / travel" value={report.total_travel_expenses} />
            <TotalStat label="Site costs" value={report.total_site_costs} />
            <TotalStat label="Total expense" value={report.total_expense} emphasize />
          </dl>

          {report.sites.length === 0 ? (
            <EmptyState message="No sites yet." />
          ) : (
            <ul className="flex flex-col gap-2">
              {report.sites.map((site) => (
                <li
                  key={site.site_id}
                  className="rounded-xl border border-slate-200 bg-white p-3 text-sm shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-slate-900">{site.site_name}</p>
                    <span className="font-semibold tabular-nums text-slate-900">
                      ₹{site.total_cost}
                    </span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500">
                    <span>Labour ₹{site.labour_cost}</span>
                    <span>Travel ₹{site.travel_expenses}</span>
                    <span>Site costs ₹{site.site_costs}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <a
            href={weeklySiteExpensesExportUrl(from, to)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-center text-sm font-medium text-brand-600 active:text-brand-700"
          >
            Download CSV
          </a>
        </>
      )}
    </div>
  )
}

function TotalStat({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={`mt-1 font-semibold text-slate-900 ${emphasize ? 'text-lg' : ''}`}>₹{value}</dd>
    </div>
  )
}
