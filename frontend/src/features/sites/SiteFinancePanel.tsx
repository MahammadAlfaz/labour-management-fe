import { useState } from 'react'
import { Field, PrimaryButton, TextInput } from '../../components/form'
import { ApiError } from '../../lib/apiClient'
import { todayIso } from '../../lib/date'
import {
  useClientReceipts,
  useCreateClientReceipt,
  useSiteFinancialSummary,
  useSiteExpenses,
} from './useSites'

function money(value: string | null | undefined) {
  return `₹${Number(value ?? 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export default function SiteFinancePanel({ siteId }: { siteId: string }) {
  const [amount, setAmount] = useState('')
  const [receivedOn, setReceivedOn] = useState(todayIso())
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { data: summary, isLoading: summaryLoading } = useSiteFinancialSummary(siteId)
  const { data: receipts } = useClientReceipts(siteId)
  const { data: siteExpenses } = useSiteExpenses(siteId)
  const receiptMutation = useCreateClientReceipt(siteId)

  async function addReceipt() {
    setError(null)
    if (!amount || Number(amount) <= 0) {
      setError('Enter an amount received from the client.')
      return
    }
    try {
      await receiptMutation.mutateAsync({ amount, received_on: receivedOn, note: note.trim() || undefined })
      setAmount('')
      setNote('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the client receipt.')
    }
  }

  return (
    <section className="border-t border-slate-200 pt-4" aria-labelledby="site-finances-title">
      <h3 id="site-finances-title" className="text-base font-semibold text-slate-900">Site finances</h3>
      <p className="mt-1 text-sm text-slate-600">
        Costs are calculated from attendance wages and travel entries. Labourer payments are not
        added again, so costs are never double-counted.
      </p>

      {summaryLoading ? (
        <p className="mt-3 text-sm text-slate-500">Loading finances…</p>
      ) : summary ? (
        <dl className="mt-3 grid grid-cols-2 gap-2">
          <FinanceValue label="Days worked" value={String(summary.days_worked)} />
          <FinanceValue label="Agreed with client" value={summary.contract_amount === null ? 'Not set' : money(summary.contract_amount)} />
          <FinanceValue label="Received from client" value={money(summary.client_received)} tone="positive" />
          <FinanceValue label="Labour cost" value={money(summary.labour_cost)} />
          <FinanceValue label="Travel cost" value={money(summary.travel_expenses)} />
          <FinanceValue label="Site costs (food etc.)" value={money(summary.site_expenses)} />
          <FinanceValue label="Total cost used" value={money(summary.total_cost)} tone="negative" />
          {summary.client_balance !== null && <FinanceValue label="Still due from client" value={money(summary.client_balance)} />}
          <FinanceValue label="Current profit / loss" value={money(summary.current_profit)} tone={Number(summary.current_profit) < 0 ? 'negative' : 'positive'} />
          {summary.expected_profit !== null && <FinanceValue label="Expected profit" value={money(summary.expected_profit)} tone={Number(summary.expected_profit) < 0 ? 'negative' : 'positive'} />}
        </dl>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 rounded-xl bg-slate-50 p-3">
        <p className="font-medium text-slate-800">Record client payment</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount" htmlFor="client-receipt-amount">
            <TextInput id="client-receipt-amount" type="number" inputMode="decimal" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
          </Field>
          <Field label="Received on" htmlFor="client-receipt-date">
            <TextInput id="client-receipt-date" type="date" value={receivedOn} onChange={(e) => setReceivedOn(e.target.value)} />
          </Field>
        </div>
        <Field label="Note (optional)" htmlFor="client-receipt-note">
          <TextInput id="client-receipt-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. First instalment" />
        </Field>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <PrimaryButton onClick={addReceipt} disabled={receiptMutation.isPending} className="w-full">
          {receiptMutation.isPending ? 'Recording…' : 'Record client payment'}
        </PrimaryButton>
      </div>

      {receipts && receipts.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-slate-700">Client payment history</h4>
          <ul className="mt-2 divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">
            {receipts.map((receipt) => (
              <li key={receipt.id} className="flex items-center justify-between gap-3 p-3 text-sm">
                <div className="min-w-0"><p className="font-medium text-slate-800">{receipt.received_on}</p>{receipt.note && <p className="truncate text-slate-500">{receipt.note}</p>}</div>
                <span className="shrink-0 font-semibold text-emerald-700">{money(receipt.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {siteExpenses && siteExpenses.length > 0 && (
        <div className="mt-4"><h4 className="text-sm font-medium text-slate-700">Site cost history</h4><ul className="mt-2 divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">{siteExpenses.map((expense) => <li key={expense.id} className="flex items-center justify-between gap-3 p-3 text-sm"><div className="min-w-0"><p className="font-medium text-slate-800">{expense.category === 'FOOD' ? 'Labour food' : 'Other site cost'} · {expense.expense_date}</p>{expense.note && <p className="truncate text-slate-500">{expense.note}</p>}</div><span className="shrink-0 font-semibold text-rose-700">{money(expense.amount)}</span></li>)}</ul></div>
      )}
    </section>
  )
}

function FinanceValue({ label, value, tone }: { label: string; value: string; tone?: 'positive' | 'negative' }) {
  const color = tone === 'positive' ? 'text-emerald-700' : tone === 'negative' ? 'text-rose-700' : 'text-slate-900'
  return <div className="rounded-xl border border-slate-200 bg-white p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className={`mt-1 font-semibold ${color}`}>{value}</dd></div>
}
