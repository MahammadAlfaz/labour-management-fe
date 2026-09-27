import { useState } from 'react'
import { PrimaryButton, SecondaryButton, Select, TextInput } from '../../components/form'
import { SearchIcon, UsersIcon } from '../../components/icons'
import { ApiError } from '../../lib/apiClient'
import { toLocalIsoDate, todayIso } from '../../lib/date'
import { buildUpiPayLink } from '../../lib/upi'
import { useLabourers } from '../labourers/useLabourers'
import { useLabourerHistory } from '../reports/useReports'
import AdvanceFormSheet from './AdvanceFormSheet'
import type { PeriodType } from './api'
import DeductionFormSheet from './DeductionFormSheet'
import { useCreatePayment, usePaymentHistory, usePaymentPreview } from './usePayments'

/** Sunday-to-Saturday week containing the given date (see plan: Sat is payday). */
function weekRange(dateStr: string): { start: string; end: string } {
  const d = new Date(`${dateStr}T00:00:00`)
  const start = new Date(d)
  start.setDate(d.getDate() - d.getDay())
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return { start: toLocalIsoDate(start), end: toLocalIsoDate(end) }
}

/** 1st to the last day of the month containing the given date. */
function monthRange(dateStr: string): { start: string; end: string } {
  const d = new Date(`${dateStr}T00:00:00`)
  const start = new Date(d.getFullYear(), d.getMonth(), 1)
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  return { start: toLocalIsoDate(start), end: toLocalIsoDate(end) }
}

function eachDayOf(startIso: string, endIso: string): string[] {
  const days: string[] = []
  const cursor = new Date(`${startIso}T00:00:00`)
  const end = new Date(`${endIso}T00:00:00`)
  while (cursor <= end) {
    days.push(toLocalIsoDate(cursor))
    cursor.setDate(cursor.getDate() + 1)
  }
  return days
}

function formatDayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  })
}

const STATUS_STYLES: Record<string, string> = {
  paid: 'bg-emerald-100 text-emerald-700',
  partial: 'bg-amber-100 text-amber-700',
  overpaid: 'bg-sky-100 text-sky-700',
}

export default function PaymentsPage() {
  const [search, setSearch] = useState('')
  const [labourerId, setLabourerId] = useState<string | null>(null)
  const [periodType, setPeriodType] = useState<PeriodType>('weekly')
  const [anchorDate, setAnchorDate] = useState(todayIso())
  const [paidAmount, setPaidAmount] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const [showAdvanceForm, setShowAdvanceForm] = useState(false)
  const [showDeductionForm, setShowDeductionForm] = useState(false)

  const { data: labourers } = useLabourers({ status: 'active', search: search.trim() || undefined })
  const selectedLabourer = labourers?.find((l) => l.id === labourerId) ?? null

  const period =
    periodType === 'daily'
      ? { start: anchorDate, end: anchorDate }
      : periodType === 'weekly'
        ? weekRange(anchorDate)
        : monthRange(anchorDate)

  const { data: preview, isLoading: previewLoading } = usePaymentPreview({
    labourerId,
    periodType,
    periodStart: period.start,
    periodEnd: period.end,
  })
  const { data: history } = usePaymentHistory(labourerId)
  const createPayment = useCreatePayment(labourerId ?? '')

  const { data: periodHistory, isLoading: periodHistoryLoading } = useLabourerHistory(
    periodType !== 'daily' ? labourerId : null,
    period.start,
    period.end
  )
  const periodDays = periodType !== 'daily' ? eachDayOf(period.start, period.end) : []
  const periodRecordsByDate = new Map((periodHistory?.work_records ?? []).map((r) => [r.work_date, r]))

  function handlePayViaUpi() {
    if (!selectedLabourer?.upi_id) return
    const amount = paidAmount || preview?.suggested_amount
    const link = buildUpiPayLink({
      payeeIdentifier: selectedLabourer.upi_id,
      payeeName: selectedLabourer.name,
      amount,
      note: `Wages for ${selectedLabourer.name}`,
    })
    window.location.href = link
  }

  async function handleSubmit() {
    if (!labourerId || !preview) return
    setError(null)
    const value = Number(paidAmount)
    if (!paidAmount || Number.isNaN(value) || value < 0) {
      setError('Enter a valid paid amount')
      return
    }
    const differs = Number(paidAmount) !== Number(preview.suggested_amount)
    if (differs && !reason.trim()) {
      setError('A reason is required when the paid amount differs from the suggested amount')
      return
    }
    try {
      await createPayment.mutateAsync({
        input: {
          labourer_id: labourerId,
          period_type: periodType,
          period_start: period.start,
          period_end: period.end,
          paid_amount: paidAmount,
          adjustment_reason: differs ? reason.trim() : undefined,
        },
        idempotencyKey,
      })
      setPaidAmount('')
      setReason('')
      setIdempotencyKey(crypto.randomUUID())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record payment')
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {!labourerId && (
        <>
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 h-5 w-5 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search a labourer to pay…"
              className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pr-3 pl-10 text-base text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            />
          </div>
          <ul className="grid grid-cols-2 gap-3">
            {labourers?.map((labourer) => (
              <li key={labourer.id}>
                <button
                  type="button"
                  onClick={() => setLabourerId(labourer.id)}
                  className="w-full cursor-pointer overflow-hidden rounded-2xl border border-slate-200 bg-white text-left shadow-sm transition-colors active:bg-slate-50"
                >
                  <div className="flex aspect-square items-center justify-center bg-slate-100">
                    {labourer.photo_url ? (
                      <img src={labourer.photo_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <UsersIcon className="h-10 w-10 text-slate-300" />
                    )}
                  </div>
                  <div className="p-2.5">
                    <p className="truncate font-semibold text-slate-900">{labourer.name}</p>
                    <p className="truncate text-xs text-slate-500">{labourer.work_category || 'General'}</p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {labourerId && selectedLabourer && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-lg font-semibold text-slate-900">{selectedLabourer.name}</p>
            <button
              type="button"
              onClick={() => setLabourerId(null)}
              className="cursor-pointer text-sm font-medium text-brand-600 active:text-brand-700"
            >
              Change
            </button>
          </div>

          <div className="flex gap-3">
            <label className="flex-1 text-sm">
              <span className="mb-1 block font-medium text-slate-700">Period</span>
              <Select value={periodType} onChange={(e) => setPeriodType(e.target.value as PeriodType)}>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly (Sun–Sat)</option>
                <option value="monthly">Monthly (1st–31st)</option>
              </Select>
            </label>
            <label className="flex-1 text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                {periodType === 'daily'
                  ? 'Date'
                  : periodType === 'weekly'
                    ? 'Any day in the week'
                    : 'Any day in the month'}
              </span>
              <TextInput
                type="date"
                value={anchorDate}
                onChange={(e) => setAnchorDate(e.target.value)}
              />
            </label>
          </div>
          {periodType !== 'daily' && (
            <p className="-mt-2 text-xs text-slate-500">
              Settling {period.start} to {period.end}
            </p>
          )}

          {periodType !== 'daily' && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="mb-2 text-sm font-semibold text-slate-900">Day by day</p>
              {periodHistoryLoading && <p className="text-sm text-slate-500">Loading…</p>}
              <ul className="flex flex-col divide-y divide-slate-100">
                {periodDays.map((day) => {
                  const record = periodRecordsByDate.get(day)
                  return (
                    <li key={day} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <div className="min-w-0">
                        <p className="font-medium text-slate-800">{formatDayLabel(day)}</p>
                        <p className="truncate text-xs text-slate-500">
                          {record ? record.site_name : 'Not worked'}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 font-semibold tabular-nums ${
                          record && Number(record.amount) > 0 ? 'text-slate-900' : 'text-slate-400'
                        }`}
                      >
                        {record ? `₹${record.amount}` : '—'}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {previewLoading && <p className="text-sm text-slate-500">Calculating…</p>}

          {preview && (
            <div className="rounded-xl bg-slate-50 p-4">
              <dl className="flex flex-col gap-1.5 text-sm">
                <Row label="Wages" value={preview.wages} />
                <Row label="Petrol & travel" value={preview.travel_expenses} />
                <Row label="Total earnings" value={preview.earnings} />
                <Row label="Advances" value={preview.unsettled_advances} negative />
                <Row label="Deductions" value={preview.unsettled_deductions} negative />
                <Row label="Adjustments" value={preview.unsettled_adjustments} signed />
                <Row label="Prior balance" value={preview.prior_balance} signed />
              </dl>
              <p className="mt-3 text-xs leading-5 text-slate-600">
                Prior balance is money still owed from earlier partial payments (or an earlier overpayment). Adjustments are corrections made after a payment was recorded.
              </p>
              {preview.adjustments.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-3">
                  <p className="text-xs font-semibold text-slate-700">Unsettled adjustments</p>
                  <ul className="mt-1.5 divide-y divide-slate-200">
                    {preview.adjustments.map((adjustment) => (
                      <li key={adjustment.id} className="flex items-center justify-between gap-3 py-2 text-xs">
                        <span className="text-slate-600">{adjustment.reason}</span>
                        <span className={`shrink-0 font-semibold tabular-nums ${Number(adjustment.amount) < 0 ? 'text-rose-600' : 'text-emerald-700'}`}>
                          {Number(adjustment.amount) >= 0 ? '+' : ''}₹{adjustment.amount}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
                <span className="font-semibold text-slate-900">Suggested amount</span>
                <span className="text-xl font-semibold tabular-nums text-slate-900">
                  ₹{preview.suggested_amount}
                </span>
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <SecondaryButton onClick={() => setShowAdvanceForm(true)} className="flex-1">
              + Advance
            </SecondaryButton>
            <SecondaryButton onClick={() => setShowDeductionForm(true)} className="flex-1">
              + Deduction
            </SecondaryButton>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4">
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">Amount to pay (₹)</span>
              <div className="flex gap-2">
                <TextInput
                  type="number"
                  inputMode="decimal"
                  min="0"
                  value={paidAmount}
                  onChange={(e) => setPaidAmount(e.target.value)}
                  placeholder="0.00"
                />
                {preview && (
                  <SecondaryButton onClick={() => setPaidAmount(preview.suggested_amount)}>
                    Use suggested
                  </SecondaryButton>
                )}
              </div>
            </label>
            {selectedLabourer.upi_id ? (
              <div className="flex flex-col gap-1">
                <SecondaryButton onClick={handlePayViaUpi} className="w-full">
                  Pay via UPI
                </SecondaryButton>
                <p className="text-xs text-slate-500">
                  Opens your UPI app with the amount pre-filled -- you still send it yourself,
                  then record the payment below.
                </p>
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Add a UPI ID for {selectedLabourer.name} (edit their profile) to pay via UPI.
              </p>
            )}
            {preview && paidAmount && Number(paidAmount) !== Number(preview.suggested_amount) && (
              <label className="text-sm">
                <span className="mb-1 block font-medium text-slate-700">
                  Reason for the difference
                </span>
                <TextInput value={reason} onChange={(e) => setReason(e.target.value)} />
              </label>
            )}
            {error && <p className="text-sm text-rose-600">{error}</p>}
            <PrimaryButton onClick={handleSubmit} disabled={createPayment.isPending} className="w-full">
              {createPayment.isPending ? 'Recording…' : 'Record payment'}
            </PrimaryButton>
          </div>

          {history && history.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-900">Payment history</h3>
              <ul className="flex flex-col gap-2">
                {history.map((payment) => (
                  <li
                    key={payment.id}
                    className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  >
                    <div>
                      <p className="text-slate-700">
                        {payment.period_start === payment.period_end
                          ? payment.period_start
                          : `${payment.period_start} – ${payment.period_end}`}
                      </p>
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[payment.status]}`}
                      >
                        {payment.status}
                      </span>
                    </div>
                    <span className="font-semibold tabular-nums text-slate-900">
                      ₹{payment.paid_amount}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {labourerId && showAdvanceForm && (
        <AdvanceFormSheet labourerId={labourerId} onClose={() => setShowAdvanceForm(false)} />
      )}
      {labourerId && showDeductionForm && (
        <DeductionFormSheet labourerId={labourerId} onClose={() => setShowDeductionForm(false)} />
      )}
    </div>
  )
}

function Row({
  label,
  value,
  negative,
  signed,
}: {
  label: string
  value: string
  negative?: boolean
  signed?: boolean
}) {
  const numeric = Number(value)
  const displayValue = negative && numeric > 0 ? `-₹${value}` : signed ? `${numeric >= 0 ? '+' : ''}₹${value}` : `₹${value}`
  const colorClass =
    (negative && numeric > 0) || (signed && numeric < 0) ? 'text-rose-600' : 'text-slate-700'

  return (
    <div className="flex items-center justify-between">
      <dt className="text-slate-500">{label}</dt>
      <dd className={`font-medium tabular-nums ${colorClass}`}>{displayValue}</dd>
    </div>
  )
}
