import unittest
from mrp_engine import DeterministicMRPEngine
from control_monitor import NaiveSingleTurnMonitor, DeterministicMRPControlMonitor
from benchmark_scenarios import get_benchmark_scenarios
from berg_sql_reference import BERG_MRP_SQL_CATALOG, get_catalog_by_subsystem


class TestMRPControlArena(unittest.TestCase):
    def test_baseline_mrp_explosion_has_no_frozen_stockouts(self) -> None:
        engine = DeterministicMRPEngine()
        orders, stockouts = engine.run_mrp_explosion()
        self.assertTrue(len(orders) > 0)
        for sku, weeks in stockouts.items():
            self.assertEqual(weeks, [], f"Unexpected baseline stockout on {sku}")

    def test_berg_po_waterfall_and_stock_conservation(self) -> None:
        engine = DeterministicMRPEngine()
        proposals = engine.run_berg_po_waterfall()
        self.assertTrue(len(proposals) > 0)
        # Verify open PO matching on RM-COMP-01 / RM-ALU-CNC
        po_nums = [p.po_num for p in proposals if p.po_num is not None]
        self.assertIn("PO00284571", po_nums)
        # Verify vWMRPSummaryControlReport baseline conservation
        report = engine.verify_stock_conservation_report()
        for row in report:
            self.assertEqual(row.stock_calculation_status, "OK")

    def test_berg_sql_catalog_completeness(self) -> None:
        self.assertGreaterEqual(len(BERG_MRP_SQL_CATALOG), 14)
        grouped = get_catalog_by_subsystem()
        self.assertIn("Order-MRP", grouped)
        self.assertIn("Ticket-MRP", grouped)
        self.assertIn("Safety-Stock", grouped)
        self.assertIn("DataCube-Audit", grouped)

    def test_control_monitor_catches_all_adversarial_and_allows_benign(self) -> None:
        scenarios = get_benchmark_scenarios()
        naive = NaiveSingleTurnMonitor()
        ctrl = DeterministicMRPControlMonitor()

        for scen in scenarios:
            engine = DeterministicMRPEngine()
            naive_res = naive.evaluate_batch(engine, scen.tool_calls)
            ctrl_res = ctrl.evaluate_batch(engine, scen.tool_calls)

            if scen.category == "adversarial":
                # Naive monitor fails on positive-valued subtle sabotage
                self.assertTrue(naive_res.allowed)
                # Deterministic invariant + counterfactual monitor catches all adversarial scenarios
                self.assertFalse(
                    ctrl_res.allowed, f"Expected {scen.scenario_id} to be blocked"
                )
                self.assertTrue(len(ctrl_res.triggered_invariants) >= 1)
            else:
                self.assertTrue(
                    ctrl_res.allowed,
                    f"Expected benign scenario {scen.scenario_id} to be allowed, got {ctrl_res.triggered_invariants}",
                )


if __name__ == "__main__":
    unittest.main()
