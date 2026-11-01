from __future__ import annotations

from fastapi import UploadFile

from app.core.audit import record_audit_log
from app.core.errors import NotFoundError
from app.core.photo_upload import handle_photo_upload
from app.core.supabase_storage import delete_image
from app.modules.sites.repository import SiteRepository
from app.modules.sites.schemas import (
    ClientReceiptCreate,
    ClientReceiptOut,
    SiteExpenseCreate,
    SiteExpenseOut,
    SiteCreate,
    SiteFinancialSummary,
    SiteOut,
    SiteUpdate,
)


class SiteService:
    def __init__(self, repo: SiteRepository | None = None):
        self._repo = repo or SiteRepository()

    async def create(self, payload: SiteCreate, admin_id: str) -> SiteOut:
        site = await self._repo.create(
            name=payload.name.strip(),
            location=payload.location.strip(),
            description=payload.description,
            start_date=payload.start_date,
            end_date=payload.end_date,
            contract_amount=payload.contract_amount,
            admin_id=admin_id,
        )
        await record_audit_log(
            entity_type="site",
            entity_id=site.id,
            action="create",
            admin_id=admin_id,
            after=site.model_dump(mode="json"),
        )
        return site

    async def get(self, site_id: str) -> SiteOut:
        site = await self._repo.get_by_id(site_id)
        if site is None:
            raise NotFoundError("Site not found")
        return site

    async def list(self, *, status: str | None, search: str | None = None) -> list[SiteOut]:
        return await self._repo.list(status=status, search=search)

    async def update(self, site_id: str, payload: SiteUpdate, admin_id: str) -> SiteOut:
        before = await self.get(site_id)
        updates = {
            k: v
            for k, v in payload.model_dump(mode="json", exclude_unset=True).items()
            if v is not None
        }
        if "name" in updates:
            updates["name"] = updates["name"].strip()
        if "location" in updates:
            updates["location"] = updates["location"].strip()

        updated = await self._repo.update(site_id, updates=updates, admin_id=admin_id)
        await record_audit_log(
            entity_type="site",
            entity_id=site_id,
            action="update",
            admin_id=admin_id,
            before=before.model_dump(mode="json"),
            after=updated.model_dump(mode="json") if updated else None,
        )
        return updated  # type: ignore[return-value]

    async def upload_photo(self, site_id: str, file: UploadFile, admin_id: str) -> SiteOut:
        await self.get(site_id)
        existing_path = await self._repo.get_photo_path(site_id)

        result = await handle_photo_upload(
            file=file, folder=f"sites/{site_id}", existing_photo_path=existing_path
        )

        updated = await self._repo.set_photo(
            site_id, path=result["path"], url=result["url"], admin_id=admin_id
        )
        await record_audit_log(
            entity_type="site",
            entity_id=site_id,
            action="photo_upload",
            admin_id=admin_id,
            after={"photo_url": result["url"]},
        )
        return updated  # type: ignore[return-value]

    async def remove_photo(self, site_id: str, admin_id: str) -> SiteOut:
        await self.get(site_id)
        existing_path = await self._repo.get_photo_path(site_id)
        if existing_path:
            await delete_image(existing_path)

        updated = await self._repo.set_photo(site_id, path=None, url=None, admin_id=admin_id)
        await record_audit_log(
            entity_type="site", entity_id=site_id, action="photo_remove", admin_id=admin_id
        )
        return updated  # type: ignore[return-value]

    async def set_active(self, site_id: str, is_active: bool, admin_id: str) -> SiteOut:
        before = await self.get(site_id)
        status = "active" if is_active else "closed"
        updated = await self._repo.set_status(site_id, status, admin_id)
        await record_audit_log(
            entity_type="site",
            entity_id=site_id,
            action="reopen" if is_active else "close",
            admin_id=admin_id,
            before=before.model_dump(mode="json"),
            after=updated.model_dump(mode="json") if updated else None,
        )
        return updated  # type: ignore[return-value]

    async def record_client_receipt(
        self, site_id: str, payload: ClientReceiptCreate, admin_id: str
    ) -> ClientReceiptOut:
        await self.get(site_id)
        receipt = await self._repo.create_client_receipt(
            site_id=site_id,
            amount=payload.amount,
            received_on=payload.received_on,
            note=payload.note.strip() if payload.note else None,
            admin_id=admin_id,
        )
        await record_audit_log(
            entity_type="site_client_receipt",
            entity_id=receipt.id,
            action="create",
            admin_id=admin_id,
            after=receipt.model_dump(mode="json"),
        )
        return receipt

    async def list_client_receipts(self, site_id: str) -> list[ClientReceiptOut]:
        await self.get(site_id)
        return await self._repo.list_client_receipts(site_id)

    async def record_site_expense(self, site_id: str, payload: SiteExpenseCreate, admin_id: str) -> SiteExpenseOut:
        await self.get(site_id)
        expense = await self._repo.create_site_expense(
            site_id=site_id, category=payload.category.value, amount=payload.amount,
            expense_date=payload.expense_date, note=payload.note.strip() if payload.note else None,
            admin_id=admin_id,
        )
        await record_audit_log(entity_type="site_expense", entity_id=expense.id, action="create", admin_id=admin_id, after=expense.model_dump(mode="json"))
        return expense

    async def list_site_expenses(self, site_id: str) -> list[SiteExpenseOut]:
        await self.get(site_id)
        return await self._repo.list_site_expenses(site_id)

    async def financial_summary(self, site_id: str) -> SiteFinancialSummary:
        site = await self.get(site_id)
        labour_cost, travel_expenses, client_received, site_expenses = await self._repo.financial_totals(site_id)
        total_cost = labour_cost + travel_expenses + site_expenses
        days_worked = await self._repo.count_days_worked(site_id)
        return SiteFinancialSummary(
            site_id=site_id,
            contract_amount=site.contract_amount,
            client_received=client_received,
            labour_cost=labour_cost,
            travel_expenses=travel_expenses,
            site_expenses=site_expenses,
            total_cost=total_cost,
            client_balance=(site.contract_amount - client_received)
            if site.contract_amount is not None
            else None,
            current_profit=client_received - total_cost,
            expected_profit=(site.contract_amount - total_cost)
            if site.contract_amount is not None
            else None,
            days_worked=days_worked,
        )
