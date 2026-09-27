import { useQuery } from '@tanstack/react-query'
import { getLabourerHistory, getSiteAttendance, getWeeklySettlement, getWeeklySiteExpenses } from './api'

export function useLabourerHistory(labourerId: string | null, from: string, to: string) {
  return useQuery({
    queryKey: ['reports', 'labourer-history', labourerId, from, to],
    queryFn: () => getLabourerHistory(labourerId as string, from, to),
    enabled: labourerId !== null,
  })
}

export function useSiteAttendanceReport(siteId: string | null, from: string, to: string) {
  return useQuery({
    queryKey: ['reports', 'site-attendance', siteId, from, to],
    queryFn: () => getSiteAttendance(siteId as string, from, to),
    enabled: siteId !== null,
  })
}

export function useWeeklySettlementReport(from: string, to: string) {
  return useQuery({
    queryKey: ['reports', 'weekly-settlement', from, to],
    queryFn: () => getWeeklySettlement(from, to),
  })
}

export function useWeeklySiteExpensesReport(from: string, to: string) {
  return useQuery({
    queryKey: ['reports', 'site-expenses', from, to],
    queryFn: () => getWeeklySiteExpenses(from, to),
  })
}
