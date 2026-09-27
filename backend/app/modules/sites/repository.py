from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from bson import ObjectId
from bson.decimal128 import Decimal128

from app.core.money import from_decimal128, to_decimal128, to_money, zero
from app.db import get_database
from app.modules.sites.schemas import ClientReceiptOut, SiteExpenseOut, SiteOut


def _date_or_none(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _extract_total(rows: list[dict]) -> Decimal:
    # $sum over zero matching documents returns no group in real MongoDB
    # (rows == []), but some drivers/test doubles synthesize a {"total": 0}
    # row instead -- handle both shapes, and both Decimal128 and
    # plain-numeric total values, uniformly.
    if not rows:
        return zero()
    total = rows[0]["total"]
    if isinstance(total, Decimal128):
        return from_decimal128(total) or zero()
    return to_money(total)


def _to_out(doc: dict) -> SiteOut:
    return SiteOut(
        id=str(doc["_id"]),
        name=doc["name"],
        location=doc["location"],
        description=doc.get("description"),
        status=doc["status"],
        start_date=_date_or_none(doc.get("start_date")),
        end_date=_date_or_none(doc.get("end_date")),
        contract_amount=from_decimal128(doc.get("contract_amount")),
        photo_url=doc.get("photo_url"),
        created_by=doc["created_by"],
        updated_by=doc["updated_by"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _receipt_to_out(doc: dict) -> ClientReceiptOut:
    return ClientReceiptOut(
        id=str(doc["_id"]),
        site_id=doc["site_id"],
        amount=from_decimal128(doc["amount"]),
        received_on=date.fromisoformat(doc["received_on"]),
        note=doc.get("note"),
        created_by=doc["created_by"],
        created_at=doc["created_at"],
    )


def _expense_to_out(doc: dict) -> SiteExpenseOut:
    return SiteExpenseOut(
        id=str(doc["_id"]), site_id=doc["site_id"], category=doc["category"],
        amount=from_decimal128(doc["amount"]), expense_date=date.fromisoformat(doc["expense_date"]),
        note=doc.get("note"), created_by=doc["created_by"], created_at=doc["created_at"],
    )


class SiteRepository:
    def __init__(self) -> None:
        self._collection = get_database().sites

    async def create(
        self,
        *,
        name: str,
        location: str,
        description: str | None,
        start_date: date | None,
        end_date: date | None,
        contract_amount: Decimal | None,
        admin_id: str,
    ) -> SiteOut:
        now = datetime.now(timezone.utc)
        doc = {
            "name": name,
            "location": location,
            "description": description,
            "status": "active",
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "contract_amount": to_decimal128(contract_amount) if contract_amount is not None else None,
            "created_by": admin_id,
            "updated_by": admin_id,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _to_out(doc)

    async def get_by_id(self, site_id: str) -> SiteOut | None:
        if not ObjectId.is_valid(site_id):
            return None
        doc = await self._collection.find_one({"_id": ObjectId(site_id)})
        return _to_out(doc) if doc else None

    async def list(self, *, status: str | None = None, search: str | None = None) -> list[SiteOut]:
        query: dict = {}
        if status:
            query["status"] = status
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
        cursor = self._collection.find(query).sort("name", 1)
        return [_to_out(doc) async for doc in cursor]

    async def update(self, site_id: str, *, updates: dict, admin_id: str) -> SiteOut | None:
        if "contract_amount" in updates and updates["contract_amount"] is not None:
            updates = {**updates, "contract_amount": to_decimal128(updates["contract_amount"])}
        updates_with_meta = {
            **updates,
            "updated_by": admin_id,
            "updated_at": datetime.now(timezone.utc),
        }
        await self._collection.update_one({"_id": ObjectId(site_id)}, {"$set": updates_with_meta})
        return await self.get_by_id(site_id)

    async def set_status(self, site_id: str, status: str, admin_id: str) -> SiteOut | None:
        return await self.update(site_id, updates={"status": status}, admin_id=admin_id)

    async def get_photo_path(self, site_id: str) -> str | None:
        doc = await self._collection.find_one(
            {"_id": ObjectId(site_id)}, projection={"photo_path": 1}
        )
        return doc.get("photo_path") if doc else None

    async def set_photo(
        self, site_id: str, *, path: str | None, url: str | None, admin_id: str
    ) -> SiteOut | None:
        return await self.update(
            site_id, updates={"photo_path": path, "photo_url": url}, admin_id=admin_id
        )

    async def create_client_receipt(
        self, *, site_id: str, amount: Decimal, received_on: date, note: str | None, admin_id: str
    ) -> ClientReceiptOut:
        doc = {
            "site_id": site_id,
            "amount": to_decimal128(amount),
            "received_on": received_on.isoformat(),
            "note": note,
            "created_by": admin_id,
            "created_at": datetime.now(timezone.utc),
        }
        result = await get_database().site_client_receipts.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _receipt_to_out(doc)

    async def list_client_receipts(self, site_id: str) -> list[ClientReceiptOut]:
        cursor = get_database().site_client_receipts.find({"site_id": site_id}).sort("received_on", -1)
        return [_receipt_to_out(doc) async for doc in cursor]

    async def create_site_expense(
        self, *, site_id: str, category: str, amount: Decimal, expense_date: date, note: str | None, admin_id: str
    ) -> SiteExpenseOut:
        doc = {"site_id": site_id, "category": category, "amount": to_decimal128(amount),
               "expense_date": expense_date.isoformat(), "note": note, "created_by": admin_id,
               "created_at": datetime.now(timezone.utc)}
        result = await get_database().site_expenses.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _expense_to_out(doc)

    async def list_site_expenses(self, site_id: str) -> list[SiteExpenseOut]:
        cursor = get_database().site_expenses.find({"site_id": site_id}).sort("expense_date", -1)
        return [_expense_to_out(doc) async for doc in cursor]

    async def financial_totals(self, site_id: str) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Return accrued labour, travel, and client receipts for one site.

        Payments are intentionally not added to labour cost: they settle the
        same wages/expenses and would otherwise double-count the expense.
        """
        db = get_database()
        labour_result = await db.daily_work_records.aggregate(
            [{"$match": {"site_id": site_id}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
        ).to_list(length=1)
        labour = _extract_total(labour_result)

        travel_result = await db.daily_work_records.aggregate(
            [
                {"$match": {"site_id": site_id}},
                {"$project": {"record_id": {"$toString": "$_id"}}},
                {"$lookup": {"from": "travel_expenses", "localField": "record_id", "foreignField": "daily_work_record_id", "as": "expenses"}},
                {"$unwind": "$expenses"},
                {"$group": {"_id": None, "total": {"$sum": "$expenses.amount"}}},
            ]
        ).to_list(length=1)
        travel = _extract_total(travel_result)

        receipts_result = await db.site_client_receipts.aggregate(
            [{"$match": {"site_id": site_id}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
        ).to_list(length=1)
        receipts = _extract_total(receipts_result)
        site_expense_result = await db.site_expenses.aggregate(
            [{"$match": {"site_id": site_id}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
        ).to_list(length=1)
        site_expenses = _extract_total(site_expense_result)
        return labour, travel, receipts, site_expenses

    async def expense_totals_for_range(
        self, site_id: str, start: date, end: date
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Labour, travel, and site-cost totals for one site within a date
        range -- the date-scoped counterpart to financial_totals, used for
        period reports (e.g. a weekly expense breakdown) rather than an
        all-time cumulative summary. Client receipts aren't part of this;
        this is purely the expense side.
        """
        db = get_database()
        date_range = {"$gte": start.isoformat(), "$lte": end.isoformat()}

        labour_result = await db.daily_work_records.aggregate(
            [
                {"$match": {"site_id": site_id, "work_date": date_range}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        ).to_list(length=1)
        labour = _extract_total(labour_result)

        travel_result = await db.daily_work_records.aggregate(
            [
                {"$match": {"site_id": site_id, "work_date": date_range}},
                {"$project": {"record_id": {"$toString": "$_id"}}},
                {"$lookup": {"from": "travel_expenses", "localField": "record_id", "foreignField": "daily_work_record_id", "as": "expenses"}},
                {"$unwind": "$expenses"},
                {"$group": {"_id": None, "total": {"$sum": "$expenses.amount"}}},
            ]
        ).to_list(length=1)
        travel = _extract_total(travel_result)

        site_expense_result = await db.site_expenses.aggregate(
            [
                {"$match": {"site_id": site_id, "expense_date": date_range}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        ).to_list(length=1)
        site_costs = _extract_total(site_expense_result)

        return labour, travel, site_costs
