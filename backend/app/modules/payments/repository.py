from datetime import date, datetime, timezone
from decimal import Decimal

from bson import ObjectId

from app.core.money import from_decimal128, to_decimal128, zero
from app.db import get_database
from app.modules.payments.schemas import PaymentOut, PaymentSnapshot


def _snapshot_to_doc(snapshot: PaymentSnapshot) -> dict:
    return {
        "wages": to_decimal128(snapshot.wages),
        "travel_expenses": to_decimal128(snapshot.travel_expenses),
        "earnings": to_decimal128(snapshot.earnings),
        "unsettled_advances": to_decimal128(snapshot.unsettled_advances),
        "unsettled_deductions": to_decimal128(snapshot.unsettled_deductions),
        "unsettled_adjustments": to_decimal128(snapshot.unsettled_adjustments),
        "prior_balance": to_decimal128(snapshot.prior_balance),
        "suggested_amount": to_decimal128(snapshot.suggested_amount),
    }


def _doc_to_snapshot(doc: dict) -> PaymentSnapshot:
    travel_expenses = from_decimal128(doc.get("travel_expenses")) or zero()
    earnings = from_decimal128(doc["earnings"])
    return PaymentSnapshot(
        # Old payment snapshots did not retain the split. Preserve them as
        # wages-only rather than making historical payments unreadable.
        wages=from_decimal128(doc.get("wages")) or earnings - travel_expenses,
        travel_expenses=travel_expenses,
        earnings=earnings,
        unsettled_advances=from_decimal128(doc["unsettled_advances"]),
        unsettled_deductions=from_decimal128(doc["unsettled_deductions"]),
        unsettled_adjustments=from_decimal128(doc["unsettled_adjustments"]),
        prior_balance=from_decimal128(doc["prior_balance"]),
        suggested_amount=from_decimal128(doc["suggested_amount"]),
    )


def _to_out(doc: dict) -> PaymentOut:
    return PaymentOut(
        id=str(doc["_id"]),
        labourer_id=doc["labourer_id"],
        period_type=doc["period_type"],
        period_start=date.fromisoformat(doc["period_start"]),
        period_end=date.fromisoformat(doc["period_end"]),
        calculation_snapshot=_doc_to_snapshot(doc["calculation_snapshot"]),
        paid_amount=from_decimal128(doc["paid_amount"]),
        adjustment_reason=doc.get("adjustment_reason"),
        status=doc["status"],
        created_by=doc["created_by"],
        created_at=doc["created_at"],
    )


class PaymentRepository:
    def __init__(self) -> None:
        self._collection = get_database().payments

    async def find_by_idempotency_key(self, key: str) -> PaymentOut | None:
        doc = await self._collection.find_one({"idempotency_key": key})
        return _to_out(doc) if doc else None

    async def create(
        self,
        *,
        labourer_id: str,
        period_type: str,
        period_start: date,
        period_end: date,
        snapshot: PaymentSnapshot,
        paid_amount: Decimal,
        adjustment_reason: str | None,
        status: str,
        admin_id: str,
        idempotency_key: str | None,
    ) -> PaymentOut:
        doc = {
            "labourer_id": labourer_id,
            "period_type": period_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "calculation_snapshot": _snapshot_to_doc(snapshot),
            "paid_amount": to_decimal128(paid_amount),
            "adjustment_reason": adjustment_reason,
            "status": status,
            "idempotency_key": idempotency_key,
            "created_by": admin_id,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _to_out(doc)

    async def get_by_id(self, payment_id: str) -> PaymentOut | None:
        if not ObjectId.is_valid(payment_id):
            return None
        doc = await self._collection.find_one({"_id": ObjectId(payment_id)})
        return _to_out(doc) if doc else None

    async def list_for_labourer(self, labourer_id: str) -> list[PaymentOut]:
        cursor = self._collection.find({"labourer_id": labourer_id}).sort(
            [("period_end", -1), ("_id", -1)]
        )
        return [_to_out(doc) async for doc in cursor]

    async def sum_balance(self, labourer_id: str) -> Decimal:
        """Accumulated (suggested - paid) across all past payments.

        Positive means still owed to the labourer (underpaid); negative means
        the labourer was overpaid and it should reduce the next payable.

        Each payment's own `suggested_amount` already has the prior balance at
        the time it was created folded into it, so that prior balance must be
        subtracted back out here before comparing to what was actually paid.
        Otherwise a shortfall that gets rolled into a later suggested amount
        and paid off there keeps getting re-counted on top of itself forever.
        """
        balance = zero()
        for payment in await self.list_for_labourer(labourer_id):
            snapshot = payment.calculation_snapshot
            balance += (snapshot.suggested_amount - snapshot.prior_balance) - payment.paid_amount
        return balance
