from datetime import date

from app.core.errors import NotFoundError
from app.core.money import zero
from app.modules.attendance.repository import WorkRecordRepository
from app.modules.expenses.repository import ExpenseRepository
from app.modules.labourers.repository import LabourerRepository
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import PeriodType
from app.modules.payments.service import PaymentService
from app.modules.reports.schemas import (
    LabourerHistoryReport,
    LabourerHistoryWorkRecord,
    SiteAttendanceEntry,
    SiteAttendanceReport,
    SiteExpenseBreakdown,
    WeeklyExpenseReport,
    WeeklySettlementEntry,
    WeeklySettlementReport,
)
from app.modules.sites.repository import SiteRepository


class ReportService:
    def __init__(
        self,
        work_record_repo: WorkRecordRepository | None = None,
        expense_repo: ExpenseRepository | None = None,
        labourer_repo: LabourerRepository | None = None,
        site_repo: SiteRepository | None = None,
        payment_repo: PaymentRepository | None = None,
        payment_service: PaymentService | None = None,
    ):
        self._work_record_repo = work_record_repo or WorkRecordRepository()
        self._expense_repo = expense_repo or ExpenseRepository()
        self._labourer_repo = labourer_repo or LabourerRepository()
        self._site_repo = site_repo or SiteRepository()
        self._payment_repo = payment_repo or PaymentRepository()
        self._payment_service = payment_service or PaymentService()

    async def labourer_history(
        self, labourer_id: str, start: date, end: date
    ) -> LabourerHistoryReport:
        labourer = await self._labourer_repo.get_by_id(labourer_id)
        if labourer is None:
            raise NotFoundError("Labourer not found")

        records = await self._work_record_repo.list_for_labourer_in_range(labourer_id, start, end)
        site_names: dict[str, str] = {}
        entries: list[LabourerHistoryWorkRecord] = []
        total_earnings = zero()

        for record in records:
            if record.site_id not in site_names:
                site = await self._site_repo.get_by_id(record.site_id)
                site_names[record.site_id] = site.name if site else "Unknown site"
            expenses_total = await self._expense_repo.sum_for_record(record.id)
            total_earnings += record.amount + expenses_total
            entries.append(
                LabourerHistoryWorkRecord(
                    id=record.id,
                    work_date=record.work_date,
                    site_id=record.site_id,
                    site_name=site_names[record.site_id],
                    status=record.status,
                    amount=record.amount,
                    expenses_total=expenses_total,
                    paid=record.payment_id is not None,
                )
            )

        all_payments = await self._payment_repo.list_for_labourer(labourer_id)
        payments_in_range = [
            p for p in all_payments if p.period_start <= end and p.period_end >= start
        ]

        # Reusing the payment engine's preview gives a consistent "if paid now"
        # outstanding figure without duplicating the settlement math here.
        preview = await self._payment_service.preview(labourer_id, PeriodType.DAILY, start, end)

        return LabourerHistoryReport(
            labourer_id=labourer_id,
            labourer_name=labourer.name,
            period_start=start,
            period_end=end,
            work_records=entries,
            payments=payments_in_range,
            total_earnings=total_earnings,
            outstanding_balance=preview.suggested_amount,
        )

    async def site_attendance(self, site_id: str, start: date, end: date) -> SiteAttendanceReport:
        site = await self._site_repo.get_by_id(site_id)
        if site is None:
            raise NotFoundError("Site not found")

        records = await self._work_record_repo.list_for_site_in_range(site_id, start, end)
        labourer_names: dict[str, str] = {}
        entries: list[SiteAttendanceEntry] = []
        total_amount = zero()

        for record in records:
            if record.labourer_id not in labourer_names:
                labourer = await self._labourer_repo.get_by_id(record.labourer_id)
                labourer_names[record.labourer_id] = labourer.name if labourer else "Unknown"
            total_amount += record.amount
            entries.append(
                SiteAttendanceEntry(
                    work_date=record.work_date,
                    labourer_id=record.labourer_id,
                    labourer_name=labourer_names[record.labourer_id],
                    status=record.status,
                    amount=record.amount,
                )
            )

        return SiteAttendanceReport(
            site_id=site_id,
            site_name=site.name,
            period_start=start,
            period_end=end,
            entries=entries,
            total_amount=total_amount,
        )

    async def weekly_settlement(self, period_start: date, period_end: date) -> WeeklySettlementReport:
        labourers = await self._labourer_repo.list(status="active", search=None)
        entries: list[WeeklySettlementEntry] = []

        for labourer in labourers:
            preview = await self._payment_service.preview(
                labourer.id, PeriodType.WEEKLY, period_start, period_end
            )
            entries.append(
                WeeklySettlementEntry(
                    labourer_id=labourer.id,
                    labourer_name=labourer.name,
                    suggested_amount=preview.suggested_amount,
                    has_unpaid_earnings=len(preview.unpaid_work_record_ids) > 0,
                )
            )

        return WeeklySettlementReport(period_start=period_start, period_end=period_end, entries=entries)

    async def weekly_site_expenses(self, period_start: date, period_end: date) -> WeeklyExpenseReport:
        """Labour, travel, and site-cost breakdown per site for a period --
        "which site cost how much" -- covering every site regardless of
        current status, since a site closed mid-period still had real costs.
        """
        sites = await self._site_repo.list(status=None)
        breakdowns: list[SiteExpenseBreakdown] = []
        total_labour = zero()
        total_travel = zero()
        total_site_costs = zero()

        for site in sites:
            labour, travel, site_costs = await self._site_repo.expense_totals_for_range(
                site.id, period_start, period_end
            )
            total_labour += labour
            total_travel += travel
            total_site_costs += site_costs
            breakdowns.append(
                SiteExpenseBreakdown(
                    site_id=site.id,
                    site_name=site.name,
                    labour_cost=labour,
                    travel_expenses=travel,
                    site_costs=site_costs,
                    total_cost=labour + travel + site_costs,
                )
            )

        breakdowns.sort(key=lambda b: b.total_cost, reverse=True)

        return WeeklyExpenseReport(
            period_start=period_start,
            period_end=period_end,
            sites=breakdowns,
            total_labour_cost=total_labour,
            total_travel_expenses=total_travel,
            total_site_costs=total_site_costs,
            total_expense=total_labour + total_travel + total_site_costs,
        )
