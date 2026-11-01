from datetime import date

import pytest

from app.core.errors import NotFoundError
from app.modules.attendance.repository import WorkRecordRepository
from app.modules.attendance.schemas import AttendanceStatus, WorkRecordAssign, WorkRecordUpdate
from app.modules.attendance.service import AttendanceService
from app.modules.labourers.repository import LabourerRepository
from app.modules.labourers.schemas import LabourerCreate
from app.modules.labourers.service import LabourerService
from app.modules.sites.repository import SiteRepository
from app.modules.sites.schemas import ClientReceiptCreate, SiteCreate, SiteExpenseCreate, SiteUpdate
from app.modules.sites.service import SiteService
from app.modules.wages.repository import WageRepository
from app.modules.wages.schemas import WageCreate
from app.modules.wages.service import WageService

UNKNOWN_SITE_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def service(mongo_db):
    return SiteService(SiteRepository())


@pytest.fixture
def attendance_service(mongo_db):
    return AttendanceService(
        WorkRecordRepository(),
        LabourerRepository(),
        SiteRepository(),
        WageService(WageRepository(), LabourerRepository()),
    )


@pytest.fixture
async def two_labourers_with_wage(mongo_db):
    labourer_service = LabourerService(LabourerRepository())
    wage_service = WageService(WageRepository(), LabourerRepository())
    labourers = []
    for name in ("Worker One", "Worker Two"):
        labourer = await labourer_service.create(LabourerCreate(name=name), "admin-1")
        await wage_service.add_wage(
            labourer.id, WageCreate(daily_wage="800", effective_from=date(2026, 1, 1)), "admin-1"
        )
        labourers.append(labourer)
    return labourers


async def _mark(attendance_service, labourer_id, site_id, work_date, status):
    assigned = await attendance_service.assign(
        WorkRecordAssign(labourer_id=labourer_id, site_id=site_id, work_date=work_date), "admin-1"
    )
    return await attendance_service.update(assigned.id, WorkRecordUpdate(status=status), "admin-1")


async def test_create_site_defaults_to_active(service):
    site = await service.create(SiteCreate(name="Tower A", location="Sector 12"), "admin-1")

    assert site.status == "active"
    assert site.name == "Tower A"


async def test_close_then_reopen_round_trip(service):
    site = await service.create(SiteCreate(name="Tower B", location="Sector 9"), "admin-1")

    closed = await service.set_active(site.id, False, "admin-1")
    assert closed.status == "closed"

    reopened = await service.set_active(site.id, True, "admin-1")
    assert reopened.status == "active"


async def test_list_filters_by_status(service):
    await service.create(SiteCreate(name="Open Site", location="X"), "admin-1")
    closed = await service.create(SiteCreate(name="Closed Site", location="Y"), "admin-1")
    await service.set_active(closed.id, False, "admin-1")

    active_only = await service.list(status="active")

    assert {site.name for site in active_only} == {"Open Site"}


async def test_list_filters_by_partial_case_insensitive_name_search(service):
    await service.create(SiteCreate(name="Sampath Kumar", location="Kundapura"), "admin-1")
    await service.create(SiteCreate(name="Siriyara Bavi", location="Siriyara"), "admin-1")

    results = await service.list(status=None, search="sampath")

    assert {site.name for site in results} == {"Sampath Kumar"}


async def test_update_persists_optional_dates(service):
    site = await service.create(SiteCreate(name="Tower C", location="Z"), "admin-1")

    updated = await service.update(
        site.id, SiteUpdate(description="Foundation work"), "admin-1"
    )

    assert updated.description == "Foundation work"


async def test_recording_client_receipt_preserves_a_history(service):
    site = await service.create(
        SiteCreate(name="Tower D", location="Pune", contract_amount="100000"), "admin-1"
    )

    receipt = await service.record_client_receipt(
        site.id,
        ClientReceiptCreate(
            amount="25000", received_on="2026-02-01", note="First instalment"
        ),
        "admin-1",
    )

    assert receipt.amount == 25000
    assert (await service.list_client_receipts(site.id))[0].id == receipt.id


async def test_get_unknown_site_raises_not_found(service):
    with pytest.raises(NotFoundError):
        await service.get(UNKNOWN_SITE_ID)


async def test_update_unknown_site_raises_not_found(service):
    with pytest.raises(NotFoundError):
        await service.update(UNKNOWN_SITE_ID, SiteUpdate(description="x"), "admin-1")


async def test_record_client_receipt_for_unknown_site_raises_not_found(service):
    with pytest.raises(NotFoundError):
        await service.record_client_receipt(
            UNKNOWN_SITE_ID,
            ClientReceiptCreate(amount="1000", received_on="2026-02-01"),
            "admin-1",
        )


async def test_record_site_expense_for_unknown_site_raises_not_found(service):
    with pytest.raises(NotFoundError):
        await service.record_site_expense(
            UNKNOWN_SITE_ID,
            SiteExpenseCreate(category="FOOD", amount="500", expense_date="2026-02-01"),
            "admin-1",
        )


async def test_record_and_list_site_expenses(service):
    site = await service.create(SiteCreate(name="Tower E", location="Pune"), "admin-1")

    expense = await service.record_site_expense(
        site.id,
        SiteExpenseCreate(category="FOOD", amount="1500", expense_date="2026-02-01", note="Lunch"),
        "admin-1",
    )

    assert expense.amount == 1500
    listed = await service.list_site_expenses(site.id)
    assert len(listed) == 1
    assert listed[0].id == expense.id


async def test_financial_summary_with_no_contract_amount(service):
    site = await service.create(SiteCreate(name="Tower F", location="Pune"), "admin-1")

    summary = await service.financial_summary(site.id)

    assert summary.contract_amount is None
    assert summary.client_balance is None
    assert summary.expected_profit is None
    assert summary.current_profit == 0
    assert summary.total_cost == 0
    assert summary.days_worked == 0


async def test_financial_summary_aggregates_receipts_and_site_expenses(service):
    site = await service.create(
        SiteCreate(name="Tower G", location="Pune", contract_amount="50000"), "admin-1"
    )
    await service.record_client_receipt(
        site.id, ClientReceiptCreate(amount="20000", received_on="2026-02-01"), "admin-1"
    )
    await service.record_client_receipt(
        site.id, ClientReceiptCreate(amount="10000", received_on="2026-02-10"), "admin-1"
    )
    await service.record_site_expense(
        site.id, SiteExpenseCreate(category="FOOD", amount="2000", expense_date="2026-02-01"), "admin-1"
    )
    await service.record_site_expense(
        site.id, SiteExpenseCreate(category="OTHER", amount="500", expense_date="2026-02-02"), "admin-1"
    )

    summary = await service.financial_summary(site.id)

    assert summary.client_received == 30000
    assert summary.site_expenses == 2500
    assert summary.labour_cost == 0  # no attendance recorded for this site
    assert summary.travel_expenses == 0
    assert summary.total_cost == 2500
    assert summary.current_profit == 27500  # 30000 received - 2500 cost
    assert summary.client_balance == 20000  # 50000 contract - 30000 received
    assert summary.expected_profit == 47500  # 50000 contract - 2500 cost


async def test_financial_summary_can_show_a_loss(service):
    site = await service.create(
        SiteCreate(name="Tower H", location="Pune", contract_amount="1000"), "admin-1"
    )
    await service.record_site_expense(
        site.id, SiteExpenseCreate(category="OTHER", amount="5000", expense_date="2026-02-01"), "admin-1"
    )

    summary = await service.financial_summary(site.id)

    assert summary.current_profit == -5000
    assert summary.expected_profit == -4000


async def test_days_worked_counts_distinct_dates_not_attendance_records(
    service, attendance_service, two_labourers_with_wage
):
    site = await service.create(SiteCreate(name="Tower I", location="Pune"), "admin-1")
    worker_one, worker_two = two_labourers_with_wage

    # Two labourers on the same day -- must still count as a single day.
    await _mark(attendance_service, worker_one.id, site.id, date(2026, 2, 1), AttendanceStatus.FULL_DAY)
    await _mark(attendance_service, worker_two.id, site.id, date(2026, 2, 1), AttendanceStatus.FULL_DAY)

    # A second, distinct day.
    await _mark(attendance_service, worker_one.id, site.id, date(2026, 2, 2), AttendanceStatus.FULL_DAY)

    # An absence must not count as a worked day.
    await _mark(attendance_service, worker_one.id, site.id, date(2026, 2, 3), AttendanceStatus.ABSENT)

    # An assignment that was never marked must not count either.
    await attendance_service.assign(
        WorkRecordAssign(labourer_id=worker_one.id, site_id=site.id, work_date=date(2026, 2, 4)), "admin-1"
    )

    summary = await service.financial_summary(site.id)

    assert summary.days_worked == 2
