import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BuildingIcon, CashIcon, ChartIcon, ChatIcon, ChevronRightIcon, RulerIcon, UsersIcon } from '../../components/icons'
import LabourerHistoryView from '../reports/LabourerHistoryView'
import SiteAttendanceView from '../reports/SiteAttendanceView'
import WeeklySettlementView from '../reports/WeeklySettlementView'
import WeeklySiteExpensesView from '../reports/WeeklySiteExpensesView'

const TABS = [
  { value: 'weekly', label: 'Weekly settlement', description: 'See who is due and export the week.', Icon: CashIcon },
  { value: 'expenses', label: 'Weekly expenses', description: 'Labour, travel, and site costs by site.', Icon: ChartIcon },
  { value: 'labourer', label: 'Labourer history', description: 'Review earnings, work days, and balance.', Icon: UsersIcon },
  { value: 'site', label: 'Site attendance', description: 'Review work records and site payouts.', Icon: BuildingIcon },
] as const

type Tab = (typeof TABS)[number]['value']

export default function MorePage() {
  const [tab, setTab] = useState<Tab>('weekly')

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <p className="text-sm font-medium text-brand-600">REPORTS</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Review your work</h2>
        <p className="mt-1 text-sm text-slate-600">Choose a report to view or export its records.</p>
      </div>

      <div>
        <p className="text-sm font-medium text-brand-600">TOOLS</p>
        <Link
          to="/wall-calculator"
          className="mt-2 flex min-h-20 w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm transition-colors active:bg-slate-50"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
            <RulerIcon className="h-5 w-5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-semibold text-slate-900">Wall calculator</span>
            <span className="mt-0.5 block text-sm font-normal text-slate-500">
              Measure a compound wall and calculate its cost.
            </span>
          </span>
          <ChevronRightIcon className="h-5 w-5 shrink-0 text-slate-400" />
        </Link>
        <Link
          to="/assistant"
          className="mt-2 flex min-h-20 w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm transition-colors active:bg-slate-50"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
            <ChatIcon className="h-5 w-5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-semibold text-slate-900">Assistant</span>
            <span className="mt-0.5 block text-sm font-normal text-slate-500">
              Ask questions about labourers, sites, and payments.
            </span>
          </span>
          <ChevronRightIcon className="h-5 w-5 shrink-0 text-slate-400" />
        </Link>
      </div>

      <div className="flex flex-col gap-2" role="tablist" aria-label="Reports">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            role="tab"
            aria-selected={tab === t.value}
            className={`flex min-h-20 w-full cursor-pointer items-center gap-3 rounded-2xl border p-3 text-left transition-colors ${
              tab === t.value
                ? 'border-brand-500 bg-brand-50 text-slate-900'
                : 'border-slate-200 bg-white text-slate-700 shadow-sm active:bg-slate-50'
            }`}
          >
            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tab === t.value ? 'bg-brand-500 text-white' : 'bg-slate-100 text-slate-600'}`} aria-hidden="true">
              <t.Icon className="h-5 w-5" />
            </span>
            <span className="min-w-0"><span className="block font-semibold">{t.label}</span><span className="mt-0.5 block text-sm font-normal text-slate-500">{t.description}</span></span>
          </button>
        ))}
      </div>

      <section className="border-t border-slate-200 pt-5">
        {tab === 'labourer' && <LabourerHistoryView />}
        {tab === 'site' && <SiteAttendanceView />}
        {tab === 'weekly' && <WeeklySettlementView />}
        {tab === 'expenses' && <WeeklySiteExpensesView />}
      </section>
    </div>
  )
}
