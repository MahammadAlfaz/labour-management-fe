from datetime import date

import pytest

from app.core.errors import NotFoundError
from app.modules.attendance.repository import WorkRecordRepository
from app.modules.attendance.schemas import AttendanceStatus, WorkRecordAssign, WorkRecordUpdate
from app.modules.attendance.service import AttendanceService
from app.modules.expenses.repository import ExpenseRepository
from app.modules.expenses.schemas import ExpenseCreate
from app.modules.expenses.service import ExpenseService
from app.modules.labourers.repository import LabourerRepository
from app.modules.labourers.schemas import LabourerCreate
from app.modules.labourers.service import LabourerService
from app.modules.payments.schemas import PaymentCreate, PeriodType
from app.modules.payments.service import PaymentService
from app.modules.reports.service import ReportService
from app.modules.sites.repository import SiteRepository
from app.modules.sites.schemas import SiteCreate
from app.modules.sites.service import SiteService
from app.modules.wages.repository import WageRepository
from app.modules.wages.schemas import WageCreate
from app.modules.wages.service import WageService


@pytest.fixture
async def site_id(mongo_db):
    site = await SiteService(SiteRepository()).create(SiteCreate(name="Report Site", location="Loc"), "admin-1")
    return site.id


@pytest.fixture
async def labourer_id(mongo_db):
    labourer = await LabourerService(LabourerRepository()).create(LabourerCreate(name="Report Labourer"), "admin-1")
    await WageService(WageRepository(), LabourerRepository()).add_wage(
        labourer.id, WageCreate(daily_wage="800", effective_from=date(2026, 1, 1)), "admin-1"
    )
    return labourer.id


@pytest.fixture
def attendance_service(mongo_db):
    return AttendanceService()


@pytest.fixture
def report_service(mongo_db):
    return ReportService()


async def _mark_full_day(attendance_service, labourer_id, site_id, work_date):
    assigned = await attendance_service.assign(
        WorkRecordAssign(labourer_id=labourer_id, site_id=site_id, work_date=work_date), "admin-1"
    )
    return await attendance_service.update(
        assigned.id, WorkRecordUpdate(status=AttendanceStatus.FULL_DAY), "admin-1"
    )


async def test_labourer_history_includes_records_and_totals(
    report_service, attendance_service, labourer_id, site_id
):
    record = await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await ExpenseService(ExpenseRepository(), WorkRecordRepository()).add(
        record.id, ExpenseCreate(category="PETROL", amount="50"), "admin-1"
    )

    report = await report_service.labourer_history(labourer_id, date(2026, 2, 1), date(2026, 2, 1))

    assert len(report.work_records) == 1
    assert report.work_records[0].site_name == "Report Site"
    assert report.work_records[0].expenses_total == 50
    assert report.total_earnings == 850
    assert report.outstanding_balance == 850
    assert report.work_records[0].paid is False


async def test_labourer_history_reflects_paid_status_and_payments(
    report_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await PaymentService().create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="800",
        ),
        "admin-1",
        idempotency_key="report-pay-1",
    )

    report = await report_service.labourer_history(labourer_id, date(2026, 2, 1), date(2026, 2, 1))

    assert report.work_records[0].paid is True
    assert len(report.payments) == 1
    assert report.outstanding_balance == 0


async def test_site_attendance_report_totals(report_service, attendance_service, labourer_id, site_id):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    report = await report_service.site_attendance(site_id, date(2026, 2, 1), date(2026, 2, 1))

    assert report.site_name == "Report Site"
    assert len(report.entries) == 1
    assert report.entries[0].labourer_name == "Report Labourer"
    assert report.total_amount == 800


async def test_weekly_settlement_flags_unpaid_earnings(report_service, attendance_service, labourer_id, site_id):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 2))

    report = await report_service.weekly_settlement(date(2026, 2, 1), date(2026, 2, 7))

    entry = next(e for e in report.entries if e.labourer_id == labourer_id)
    assert entry.has_unpaid_earnings is True
    assert entry.suggested_amount == 800


async def test_labourer_history_handles_pending_unmarked_record(
    report_service, attendance_service, labourer_id, site_id
):
    """A record that's assigned but not yet marked (status=None) must not crash the report."""
    await attendance_service.assign(
        WorkRecordAssign(labourer_id=labourer_id, site_id=site_id, work_date=date(2026, 2, 1)), "admin-1"
    )

    report = await report_service.labourer_history(labourer_id, date(2026, 2, 1), date(2026, 2, 1))

    assert len(report.work_records) == 1
    assert report.work_records[0].status is None
    assert report.work_records[0].amount == 0
    assert report.total_earnings == 0


async def test_site_attendance_report_handles_pending_unmarked_record(
    report_service, attendance_service, labourer_id, site_id
):
    await attendance_service.assign(
        WorkRecordAssign(labourer_id=labourer_id, site_id=site_id, work_date=date(2026, 2, 1)), "admin-1"
    )

    report = await report_service.site_attendance(site_id, date(2026, 2, 1), date(2026, 2, 1))

    assert len(report.entries) == 1
    assert report.entries[0].status is None


async def test_labourer_history_unknown_labourer_raises_not_found(report_service):
    with pytest.raises(NotFoundError):
        await report_service.labourer_history(
            "507f1f77bcf86cd799439011", date(2026, 2, 1), date(2026, 2, 28)
        )


async def test_site_attendance_unknown_site_raises_not_found(report_service):
    with pytest.raises(NotFoundError):
        await report_service.site_attendance(
            "507f1f77bcf86cd799439011", date(2026, 2, 1), date(2026, 2, 28)
        )


async def test_labourer_history_empty_range_returns_no_records(
    report_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    report = await report_service.labourer_history(labourer_id, date(2026, 3, 1), date(2026, 3, 31))

    assert report.work_records == []
    assert report.total_earnings == 0
    assert report.outstanding_balance == 0


async def test_weekly_settlement_with_no_active_labourers_is_empty(report_service, mongo_db):
    report = await report_service.weekly_settlement(date(2026, 2, 1), date(2026, 2, 7))

    assert report.entries == []


async def test_weekly_site_expenses_breaks_down_labour_travel_and_site_costs(
    report_service, attendance_service, labourer_id, site_id
):
    from app.modules.sites.schemas import SiteExpenseCreate
    from app.modules.sites.service import SiteService
    from app.modules.sites.repository import SiteRepository

    record = await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 2))
    await ExpenseService(ExpenseRepository(), WorkRecordRepository()).add(
        record.id, ExpenseCreate(category="PETROL", amount="50"), "admin-1"
    )
    await SiteService(SiteRepository()).record_site_expense(
        site_id, SiteExpenseCreate(category="FOOD", amount="200", expense_date=date(2026, 2, 2)), "admin-1"
    )

    report = await report_service.weekly_site_expenses(date(2026, 2, 1), date(2026, 2, 7))

    entry = next(s for s in report.sites if s.site_id == site_id)
    assert entry.labour_cost == 800
    assert entry.travel_expenses == 50
    assert entry.site_costs == 200
    assert entry.total_cost == 1050
    assert report.total_labour_cost == 800
    assert report.total_travel_expenses == 50
    assert report.total_site_costs == 200
    assert report.total_expense == 1050


async def test_weekly_site_expenses_excludes_costs_outside_the_period(
    report_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 1, 15))

    report = await report_service.weekly_site_expenses(date(2026, 2, 1), date(2026, 2, 7))

    entry = next(s for s in report.sites if s.site_id == site_id)
    assert entry.labour_cost == 0
    assert entry.total_cost == 0


async def test_weekly_site_expenses_includes_sites_with_zero_activity(report_service, site_id):
    report = await report_service.weekly_site_expenses(date(2026, 2, 1), date(2026, 2, 7))

    entry = next(s for s in report.sites if s.site_id == site_id)
    assert entry.total_cost == 0


async def test_weekly_site_expenses_sorts_by_total_cost_descending(
    report_service, attendance_service, labourer_id, site_id
):
    from app.modules.sites.schemas import SiteCreate, SiteExpenseCreate
    from app.modules.sites.service import SiteService
    from app.modules.sites.repository import SiteRepository

    other_site = await SiteService(SiteRepository()).create(
        SiteCreate(name="Cheaper Site", location="Loc B"), "admin-1"
    )
    await _mark_full_day(attendance_service, labourer_id, other_site.id, date(2026, 2, 3))
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 2))
    await SiteService(SiteRepository()).record_site_expense(
        site_id, SiteExpenseCreate(category="FOOD", amount="500", expense_date=date(2026, 2, 2)), "admin-1"
    )

    report = await report_service.weekly_site_expenses(date(2026, 2, 1), date(2026, 2, 7))

    totals = [s.total_cost for s in report.sites]
    assert totals == sorted(totals, reverse=True)
    assert report.sites[0].site_id == site_id
