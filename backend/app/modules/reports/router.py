import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.core.deps import get_current_admin
from app.modules.admins.schemas import AdminOut
from app.modules.reports.schemas import (
    LabourerHistoryReport,
    SiteAttendanceReport,
    WeeklyExpenseReport,
    WeeklySettlementReport,
)
from app.modules.reports.service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_response(rows: list[list[str]], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(row)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/labourer/{labourer_id}/history", response_model=LabourerHistoryReport)
async def labourer_history(
    labourer_id: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> LabourerHistoryReport:
    return await ReportService().labourer_history(labourer_id, date_from, date_to)


@router.get("/labourer/{labourer_id}/history/export")
async def export_labourer_history(
    labourer_id: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> Response:
    report = await ReportService().labourer_history(labourer_id, date_from, date_to)
    rows = [["Date", "Site", "Status", "Wage Amount", "Expenses", "Paid"]]
    for r in report.work_records:
        rows.append(
            [
                r.work_date.isoformat(),
                r.site_name,
                r.status.value if r.status else "PENDING",
                str(r.amount),
                str(r.expenses_total),
                "Yes" if r.paid else "No",
            ]
        )
    rows.append([])
    rows.append(["Total earnings", str(report.total_earnings)])
    rows.append(["Outstanding balance", str(report.outstanding_balance)])
    return _csv_response(rows, f"{report.labourer_name}-history-{date_from}-to-{date_to}.csv")


@router.get("/site/{site_id}/attendance", response_model=SiteAttendanceReport)
async def site_attendance(
    site_id: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> SiteAttendanceReport:
    return await ReportService().site_attendance(site_id, date_from, date_to)


@router.get("/site/{site_id}/attendance/export")
async def export_site_attendance(
    site_id: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> Response:
    report = await ReportService().site_attendance(site_id, date_from, date_to)
    rows = [["Date", "Labourer", "Status", "Amount"]]
    for e in report.entries:
        rows.append(
            [e.work_date.isoformat(), e.labourer_name, e.status.value if e.status else "PENDING", str(e.amount)]
        )
    rows.append([])
    rows.append(["Total", str(report.total_amount)])
    return _csv_response(rows, f"{report.site_name}-attendance-{date_from}-to-{date_to}.csv")


@router.get("/weekly-settlement", response_model=WeeklySettlementReport)
async def weekly_settlement(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> WeeklySettlementReport:
    return await ReportService().weekly_settlement(date_from, date_to)


@router.get("/weekly-settlement/export")
async def export_weekly_settlement(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> Response:
    report = await ReportService().weekly_settlement(date_from, date_to)
    rows = [["Labourer", "Suggested Amount", "Has Unpaid Earnings"]]
    for e in report.entries:
        rows.append([e.labourer_name, str(e.suggested_amount), "Yes" if e.has_unpaid_earnings else "No"])
    return _csv_response(rows, f"weekly-settlement-{date_from}-to-{date_to}.csv")


@router.get("/site-expenses", response_model=WeeklyExpenseReport)
async def weekly_site_expenses(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> WeeklyExpenseReport:
    return await ReportService().weekly_site_expenses(date_from, date_to)


@router.get("/site-expenses/export")
async def export_weekly_site_expenses(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    _current_admin: AdminOut = Depends(get_current_admin),
) -> Response:
    report = await ReportService().weekly_site_expenses(date_from, date_to)
    rows = [["Site", "Labour Cost", "Travel Expenses", "Site Costs", "Total Cost"]]
    for s in report.sites:
        rows.append(
            [s.site_name, str(s.labour_cost), str(s.travel_expenses), str(s.site_costs), str(s.total_cost)]
        )
    rows.append([])
    rows.append(["Total labour cost", str(report.total_labour_cost)])
    rows.append(["Total travel expenses", str(report.total_travel_expenses)])
    rows.append(["Total site costs", str(report.total_site_costs)])
    rows.append(["Total expense", str(report.total_expense)])
    return _csv_response(rows, f"site-expenses-{date_from}-to-{date_to}.csv")
