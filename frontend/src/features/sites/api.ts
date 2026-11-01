import { apiFetch, apiUpload } from '../../lib/apiClient'

export type SiteStatus = 'active' | 'closed'

export interface Site {
  id: string
  name: string
  location: string
  description: string | null
  status: SiteStatus
  start_date: string | null
  end_date: string | null
  contract_amount: string | null
  photo_url: string | null
  created_by: string
  updated_by: string
  created_at: string
  updated_at: string
}

export interface SiteInput {
  name: string
  location: string
  description?: string | null
  start_date?: string | null
  end_date?: string | null
  contract_amount?: string | null
}

export interface SiteFinancialSummary {
  site_id: string
  contract_amount: string | null
  client_received: string
  labour_cost: string
  travel_expenses: string
  site_expenses: string
  total_cost: string
  client_balance: string | null
  current_profit: string
  expected_profit: string | null
  days_worked: number
}

export type SiteExpenseCategory = 'FOOD' | 'OTHER'

export interface SiteExpense {
  id: string
  site_id: string
  category: SiteExpenseCategory
  amount: string
  expense_date: string
  note: string | null
  created_by: string
  created_at: string
}

export interface ClientReceipt {
  id: string
  site_id: string
  amount: string
  received_on: string
  note: string | null
  created_by: string
  created_at: string
}

export function listSites(params: { status?: string } = {}) {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  const qs = query.toString()
  return apiFetch<Site[]>(`/sites${qs ? `?${qs}` : ''}`)
}

export function createSite(input: SiteInput) {
  return apiFetch<Site>('/sites', { method: 'POST', body: JSON.stringify(input) })
}

export function updateSite(id: string, input: Partial<SiteInput>) {
  return apiFetch<Site>(`/sites/${id}`, { method: 'PATCH', body: JSON.stringify(input) })
}

export function setSiteActive(id: string, isActive: boolean) {
  return apiFetch<Site>(`/sites/${id}/${isActive ? 'reopen' : 'close'}`, { method: 'POST' })
}

export function uploadSitePhoto(id: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return apiUpload<Site>(`/sites/${id}/photo`, formData)
}

export function removeSitePhoto(id: string) {
  return apiFetch<Site>(`/sites/${id}/photo`, { method: 'DELETE' })
}

export function getSiteFinancialSummary(id: string) {
  return apiFetch<SiteFinancialSummary>(`/sites/${id}/financial-summary`)
}

export function listClientReceipts(id: string) {
  return apiFetch<ClientReceipt[]>(`/sites/${id}/client-receipts`)
}

export function createClientReceipt(
  id: string,
  input: { amount: string; received_on: string; note?: string }
) {
  return apiFetch<ClientReceipt>(`/sites/${id}/client-receipts`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function listSiteExpenses(id: string) {
  return apiFetch<SiteExpense[]>(`/sites/${id}/expenses`)
}

export function createSiteExpense(id: string, input: { category: SiteExpenseCategory; amount: string; expense_date: string; note?: string }) {
  return apiFetch<SiteExpense>(`/sites/${id}/expenses`, { method: 'POST', body: JSON.stringify(input) })
}
