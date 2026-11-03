"""
BERG Production MRP SQL Architecture & Schema Reference (`berg_sql_reference.py`).

Documents and codifies the exact production MS SQL Server tables, views, scalar/table
functions, and stored procedures from `BergTurkey` and `BergReport` (BG-DW) that power
the deterministic MRP & shop-floor scheduling state machine in `MRP-Control-Arena`.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class BergSQLObjectSpec:
    database: str
    schema: str
    name: str
    object_type: str  # "PROCEDURE", "TABLE", "VIEW", "FUNCTION"
    subsystem: str  # "Order-MRP", "Ticket-MRP", "Safety-Stock", "DataCube-Audit"
    purpose: str
    arena_mapping: str


BERG_MRP_SQL_CATALOG: List[BergSQLObjectSpec] = [
    # 1. Order-Driven Multi-Level MRP Subsystem
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="ExecuteMrpActiveTask",
        object_type="PROCEDURE",
        subsystem="Order-MRP",
        purpose=(
            "Entry-point scheduler that creates a new mrp_list run with hard-coded excluded "
            "MRB/quarantine locations ('DRL01'..'GKK13') and dispatches ExecuteMrp_BaseWhse."
        ),
        arena_mapping="DeterministicMRPEngine.EXCLUDED_MRB_LOCATIONS & INV-3d [MRB Quarantine Location Lock]",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="ExecuteMrp_BaseWhse",
        object_type="PROCEDURE",
        subsystem="Order-MRP",
        purpose=(
            "Core multi-level MRP orchestrator: archives previous mrp_co/mrp_po/mrp_bom/mrp_job/mrp_sum_po, "
            "snapshots itemvend rank=1 parameters into mrp_item_parms, loads customer orders (coitem) and "
            "safety stock ('SS-' + item from itemwhse.qty_reorder), explodes standard BOMs (job_CTE, type='S'), "
            "iterates level-by-level calling MrpWaterfallStockCO_BaseWhse, computes ETA/ETD/order_date, "
            "groups by collection_frequency into mrp_sum_po, and executes MrpWaterfallPo_BaseWhse."
        ),
        arena_mapping="DeterministicMRPEngine.run_mrp_explosion() & run_berg_po_waterfall()",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="MrpWaterfallStockCO_BaseWhse",
        object_type="PROCEDURE",
        subsystem="Order-MRP",
        purpose=(
            "Windowed running-total stock waterfall (SUM(qty) OVER (PARTITION BY item ORDER BY due_date, "
            "co_num, co_line, top_item)) that nets mrp_item_parms.qty_on_hand against gross demand at each BOM level."
        ),
        arena_mapping="DeterministicMRPEngine.run_mrp_explosion() projected_available netting loop",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="MrpUpdateItemStock_BaseWhse",
        object_type="PROCEDURE",
        subsystem="Order-MRP",
        purpose=(
            "Cross-level stock reconciliation pass after full BOM explosion for items appearing across "
            "multiple BOM levels with out-of-order due dates."
        ),
        arena_mapping="DeterministicMRPEngine.verify_stock_conservation_report()",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="MrpWaterfallPo_BaseWhse",
        object_type="PROCEDURE",
        subsystem="Order-MRP",
        purpose=(
            "Matches net purchase requirements (mrp_sum_po) against open purchase orders (poitem stat IN ('O','P','I')), "
            "rounds net shortage using CEILING(qty / order_box_qty) * order_box_qty with order_min floor, "
            "and generates expedite/deferral signals ('Rcpt Projected Late', 'Move In Rcpt', 'Move Out Rcpt', 'Receipt Not Needed')."
        ),
        arena_mapping="DeterministicMRPEngine.run_berg_po_waterfall() & round_to_order_box_and_min()",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="vWMRPSummaryControlReport",
        object_type="VIEW",
        subsystem="Order-MRP",
        purpose=(
            "Formal stock conservation audit view checking (totalorder - totalneed) <= (orj_qty_on_hand - qty_on_hand); "
            "flags 'STOCK CONSUMPTION PROBLEM' on phantom or unbacked stock consumption."
        ),
        arena_mapping="DeterministicMRPEngine.verify_stock_conservation_report() & INV-4c",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="VwQvMrpSumPoDetails",
        object_type="VIEW",
        subsystem="Order-MRP",
        purpose=(
            "QlikView / BI procurement integration view exposing MRPForecastOpeningDate, ScheduledUploadDate, "
            "MRPPurchaseAvailableStock (mrb_flag=0), and MRPPurchaseQuarantineStock (mrb_flag=1)."
        ),
        arena_mapping="MRPPurchaseProposal (eta_week, etd_week, order_release_week)",
    ),
    # 2. Ticket-Driven Shop-Floor & Mixture/Purchase MRP Subsystem
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="ExecuteMrpCalculate",
        object_type="PROCEDURE",
        subsystem="Ticket-MRP",
        purpose=(
            "Shop-floor ticket BOM explosion across 10 levels from mrp_Ticket into mrp_TicketCalculateBalance, "
            "netting production location stock (mrpCalculateProductionLoc minus MaterialTransferTuketimFarkiWithLocation) "
            "via ExecuteMrpCalculateWaterfallStockTicket."
        ),
        arena_mapping="Work-Center Ticket scheduling & multi-level dependent demand explosion",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="ExecuteMrpTicketMixtureCalculate",
        object_type="PROCEDURE",
        subsystem="Ticket-MRP",
        purpose=(
            "Calculates rubber compound (wc='90410', K-prefix) requirements from extrusion tickets (wc='90110') "
            "with a 1.1x (10%) technological buffer and 2-stage warehouse waterfall (local whse -> central whse '5')."
        ),
        arena_mapping="BOMEdge scrap_factor & multi-warehouse mixture waterfall",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="ExecuteMrpTicketPurchaseCalculate",
        object_type="PROCEDURE",
        subsystem="Ticket-MRP",
        purpose=(
            "Calculates purchased component (pmt_code='P') requirements directly from active shop-floor tickets "
            "and nets against local warehouse + central warehouse '5' (ExecuteMrpTicketPurchaseWaterfallCenterWhse)."
        ),
        arena_mapping="Purchased component netting in DeterministicMRPEngine",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="mrp_Ticket_Insert",
        object_type="PROCEDURE",
        subsystem="Ticket-MRP",
        purpose=(
            "Inserts shop-floor work-center production tickets after enforcing duplicate-ticket checks and "
            "fnMrpHasCapacityForDay(@Wc, @Qty, @PlanWorkDate) unless bypassed via @IsUncontrolled=1."
        ),
        arena_mapping="Agent tool 'insert_wc_production_ticket' & INV-5a / INV-5b",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="spmrptmpAutoTicketInsert",
        object_type="PROCEDURE",
        subsystem="Ticket-MRP",
        purpose=(
            "Auto-planner procedure that preserves active tickets inside the frozen 2-day work-calendar horizon "
            "(PlanWorkDate <= mrp_GetNextWorkDateForWc(GETDATE(), @Wc, @DeleteDayCount)) and reschedules future days."
        ),
        arena_mapping="Agent tool 'reschedule_wc_tickets_outside_frozen_window' & INV-5c",
    ),
    # 3. Safety Stock & Parameter Governance Subsystem
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="spSafetyCalculate",
        object_type="PROCEDURE",
        subsystem="Safety-Stock",
        purpose=(
            "Computes dynamic safety stock (SafetyStockComponent = ((OrderQuantity + ConsumptionQuantity)/2) * Coefficient) "
            "and percentage delta (DifferenceQuantity) across A/B/C classes in SafetyStockClassItem."
        ),
        arena_mapping="ItemMaster.safety_stock_class_id / safety_stock_coefficient & INV-3a",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="spSafetyTransfer",
        object_type="PROCEDURE",
        subsystem="Safety-Stock",
        purpose="Transfers calculated SafetyStockComponent to itemwhse.qty_reorder for non-manual classes (ClassId <> 0).",
        arena_mapping="Agent tool 'update_safety_stock' & ParameterChangeLogEntry",
    ),
    BergSQLObjectSpec(
        database="BergTurkey",
        schema="dbo",
        name="spDataCubeMrpParameterInsert",
        object_type="PROCEDURE",
        subsystem="DataCube-Audit",
        purpose=(
            "Daily snapshot extractor copying LEAD_TIME, MIN_QTY, BOX_QTY, TRANSIT_TIME, ORDER_PREP, SAFETY_STOCK "
            "(TakeBackDays vs Coefficient*7 vs MANUAL), SHIPMENT_DAY_COUNT, CUST_LEAD_TIME, and VendorSpecialCalendar "
            "into BergReport.rpt.DataCubeMRPParameter."
        ),
        arena_mapping="ParameterChangeLogEntry & INV-6a [DataCubeMRPParameter Lot-Size Governance]",
    ),
    BergSQLObjectSpec(
        database="BergReport",
        schema="rpt",
        name="spDataCubeMRPParameterLogInsert",
        object_type="PROCEDURE",
        subsystem="DataCube-Audit",
        purpose=(
            "Computes day-over-day parameter diffs (Action IN ('U','I','D'), OldValue -> NewValue, ChangeUser) "
            "across all plants into BergReport.rpt.DataCubeMRPParameterLog."
        ),
        arena_mapping="DeterministicMRPEngine.parameter_change_log",
    ),
]


def get_catalog_by_subsystem() -> Dict[str, List[BergSQLObjectSpec]]:
    grouped: Dict[str, List[BergSQLObjectSpec]] = {}
    for spec in BERG_MRP_SQL_CATALOG:
        grouped.setdefault(spec.subsystem, []).append(spec)
    return grouped
