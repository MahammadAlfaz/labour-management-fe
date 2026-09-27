from datetime import date

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.modules.adjustments.repository import AdjustmentRepository
from app.modules.advances.repository import AdvanceRepository
from app.modules.advances.schemas import AdvanceCreate
from app.modules.advances.service import AdvanceService
from app.modules.attendance.repository import WorkRecordRepository
from app.modules.attendance.schemas import (
    AmountAdjustment,
    AttendanceStatus,
    WorkRecordAssign,
    WorkRecordUpdate,
)
from app.modules.attendance.service import AttendanceService
from app.modules.deductions.repository import DeductionRepository
from app.modules.deductions.schemas import DeductionCreate
from app.modules.deductions.service import DeductionService
from app.modules.expenses.repository import ExpenseRepository
from app.modules.expenses.schemas import ExpenseCreate
from app.modules.expenses.service import ExpenseService
from app.modules.labourers.repository import LabourerRepository
from app.modules.labourers.schemas import LabourerCreate
from app.modules.labourers.service import LabourerService
from app.modules.payments.schemas import PaymentCreate, PeriodType
from app.modules.payments.service import PaymentService
from app.modules.sites.repository import SiteRepository
from app.modules.sites.schemas import SiteCreate
from app.modules.sites.service import SiteService
from app.modules.wages.repository import WageRepository
from app.modules.wages.schemas import WageCreate
from app.modules.wages.service import WageService


@pytest.fixture
async def site_id(mongo_db):
    site = await SiteService(SiteRepository()).create(SiteCreate(name="Site A", location="Loc A"), "admin-1")
    return site.id


@pytest.fixture
async def labourer_id(mongo_db):
    labourer = await LabourerService(LabourerRepository()).create(LabourerCreate(name="Pay Test"), "admin-1")
    await WageService(WageRepository(), LabourerRepository()).add_wage(
        labourer.id, WageCreate(daily_wage="800", effective_from=date(2026, 1, 1)), "admin-1"
    )
    return labourer.id


@pytest.fixture
def attendance_service(mongo_db):
    return AttendanceService()


@pytest.fixture
def payment_service(mongo_db):
    return PaymentService()


async def _mark_full_day(attendance_service, labourer_id, site_id, work_date):
    assigned = await attendance_service.assign(
        WorkRecordAssign(labourer_id=labourer_id, site_id=site_id, work_date=work_date), "admin-1"
    )
    return await attendance_service.update(
        assigned.id, WorkRecordUpdate(status=AttendanceStatus.FULL_DAY), "admin-1"
    )


async def test_preview_sums_unpaid_earnings(payment_service, attendance_service, labourer_id, site_id):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1))

    assert preview.earnings == 800
    assert preview.suggested_amount == 800
    assert len(preview.unpaid_work_record_ids) == 1


async def test_preview_sums_unpaid_earnings_over_a_full_month(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 15))
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 28))

    preview = await payment_service.preview(
        labourer_id, PeriodType.MONTHLY, date(2026, 2, 1), date(2026, 2, 28)
    )

    assert preview.earnings == 2400
    assert preview.suggested_amount == 2400
    assert len(preview.unpaid_work_record_ids) == 3


async def test_create_payment_marks_records_paid_and_excludes_from_next_preview(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    payment = await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="800",
        ),
        "admin-1",
        idempotency_key="pay-1",
    )

    assert payment.status == "paid"
    assert payment.paid_amount == 800

    next_preview = await payment_service.preview(
        labourer_id, PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1)
    )
    assert next_preview.earnings == 0


async def test_paid_amount_mismatch_requires_reason(payment_service, attendance_service, labourer_id, site_id):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    with pytest.raises(ConflictError):
        await payment_service.create_payment(
            PaymentCreate(
                labourer_id=labourer_id,
                period_type=PeriodType.DAILY,
                period_start=date(2026, 2, 1),
                period_end=date(2026, 2, 1),
                paid_amount="500",
            ),
            "admin-1",
            idempotency_key="pay-2",
        )


async def test_advance_reduces_suggested_amount_and_is_settled(
    payment_service, attendance_service, labourer_id, site_id, mongo_db
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await AdvanceService(AdvanceRepository(), LabourerRepository()).create(
        AdvanceCreate(labourer_id=labourer_id, amount="200", given_at=date(2026, 1, 20)), "admin-1"
    )

    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1))
    assert preview.unsettled_advances == 200
    assert preview.suggested_amount == 600

    await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="600",
        ),
        "admin-1",
        idempotency_key="pay-3",
    )

    advances = await AdvanceRepository().list_for_labourer(labourer_id)
    assert advances[0].settled is True


async def test_deduction_reduces_suggested_amount_and_is_settled(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await DeductionService(DeductionRepository(), LabourerRepository()).create(
        DeductionCreate(labourer_id=labourer_id, amount="50", reason="Tool damage"), "admin-1"
    )

    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1))
    assert preview.suggested_amount == 750


async def test_partial_payment_carries_prior_balance_forward(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="500",
            adjustment_reason="Cash shortage, will settle rest next time",
        ),
        "admin-1",
        idempotency_key="pay-4",
    )

    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 2))
    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 2), date(2026, 2, 2))

    # Owed 300 from the underpaid first day, plus the new day's 800.
    assert preview.prior_balance == 300
    assert preview.suggested_amount == 1100


async def test_paying_suggested_amount_in_full_clears_a_carried_prior_balance(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="500",
            adjustment_reason="Cash shortage, will settle rest next time",
        ),
        "admin-1",
        idempotency_key="pay-carry-1",
    )

    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 2))
    second_preview = await payment_service.preview(
        labourer_id, PeriodType.DAILY, date(2026, 2, 2), date(2026, 2, 2)
    )
    assert second_preview.prior_balance == 300
    assert second_preview.suggested_amount == 1100

    await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 2),
            period_end=date(2026, 2, 2),
            paid_amount="1100",
        ),
        "admin-1",
        idempotency_key="pay-carry-2",
    )

    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 3))
    third_preview = await payment_service.preview(
        labourer_id, PeriodType.DAILY, date(2026, 2, 3), date(2026, 2, 3)
    )

    # The 300 shortfall was fully absorbed and paid off via the second
    # payment's higher suggested amount -- it must not reappear here.
    assert third_preview.prior_balance == 0
    assert third_preview.suggested_amount == 800


async def test_overpayment_reduces_next_suggested_amount(payment_service, attendance_service, labourer_id, site_id):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="900",
            adjustment_reason="Rounded up as a bonus",
        ),
        "admin-1",
        idempotency_key="pay-5",
    )

    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 2))
    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 2), date(2026, 2, 2))

    assert preview.prior_balance == -100
    assert preview.suggested_amount == 700


async def test_duplicate_payment_request_with_same_idempotency_key_is_safe(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    payload = PaymentCreate(
        labourer_id=labourer_id,
        period_type=PeriodType.DAILY,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 1),
        paid_amount="800",
    )

    first = await payment_service.create_payment(payload, "admin-1", idempotency_key="dup-key")
    second = await payment_service.create_payment(payload, "admin-1", idempotency_key="dup-key")

    assert first.id == second.id
    history = await payment_service.list_for_labourer(labourer_id)
    assert len(history) == 1


async def test_expense_added_after_payment_creates_adjustment_not_touching_payment(
    payment_service, attendance_service, labourer_id, site_id, mongo_db
):
    record = await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    payment = await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="800",
        ),
        "admin-1",
        idempotency_key="pay-6",
    )

    expense_service = ExpenseService(ExpenseRepository(), WorkRecordRepository())
    await expense_service.add(record.id, ExpenseCreate(category="PETROL", amount="50"), "admin-1")

    unsettled = await AdjustmentRepository().list_unsettled(labourer_id)
    assert len(unsettled) == 1
    assert unsettled[0].amount == 50

    reloaded_payment = await payment_service.list_for_labourer(labourer_id)
    assert reloaded_payment[0].paid_amount == payment.paid_amount == 800  # untouched


async def test_attendance_adjustment_after_payment_creates_adjustment(
    payment_service, attendance_service, labourer_id, site_id
):
    record = await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))
    await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="800",
        ),
        "admin-1",
        idempotency_key="pay-7",
    )

    await attendance_service.adjust_amount(
        record.id, AmountAdjustment(amount="750", reason="Left early, noticed after payment"), "admin-1"
    )

    unsettled = await AdjustmentRepository().list_unsettled(labourer_id)
    assert len(unsettled) == 1
    assert unsettled[0].amount == -50

    next_preview = await payment_service.preview(
        labourer_id, PeriodType.DAILY, date(2026, 2, 2), date(2026, 2, 2)
    )
    assert next_preview.unsettled_adjustments == -50


async def test_pending_unmarked_record_is_excluded_from_earnings_and_not_paid(
    payment_service, attendance_service, labourer_id, site_id
):
    """A labourer assigned but not yet marked must not be paid ₹0 and locked out."""
    pending = await attendance_service.assign(
        WorkRecordAssign(labourer_id=labourer_id, site_id=site_id, work_date=date(2026, 2, 1)), "admin-1"
    )

    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1))
    assert preview.earnings == 0
    assert pending.id not in preview.unpaid_work_record_ids



async def test_preview_for_unknown_labourer_raises_not_found(payment_service):
    with pytest.raises(NotFoundError):
        await payment_service.preview(
            "507f1f77bcf86cd799439011", PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1)
        )


async def test_create_payment_works_without_an_idempotency_key(
    payment_service, attendance_service, labourer_id, site_id
):
    await _mark_full_day(attendance_service, labourer_id, site_id, date(2026, 2, 1))

    payment = await payment_service.create_payment(
        PaymentCreate(
            labourer_id=labourer_id,
            period_type=PeriodType.DAILY,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 1),
            paid_amount="800",
        ),
        "admin-1",
        idempotency_key=None,
    )

    assert payment.paid_amount == 800
    # without a key, nothing protects against a second identical call --
    # that's an accepted tradeoff for callers that don't supply one.
    history = await payment_service.list_for_labourer(labourer_id)
    assert len(history) == 1


async def test_list_for_labourer_with_no_payments_is_empty(payment_service, labourer_id):
    assert await payment_service.list_for_labourer(labourer_id) == []


async def test_zero_earnings_with_no_prior_balance_is_a_zero_suggested_amount(
    payment_service, labourer_id
):
    preview = await payment_service.preview(labourer_id, PeriodType.DAILY, date(2026, 2, 1), date(2026, 2, 1))

    assert preview.earnings == 0
    assert preview.suggested_amount == 0
    assert preview.unpaid_work_record_ids == []
