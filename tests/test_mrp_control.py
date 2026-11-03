import unittest
from mrp_engine import DeterministicMRPEngine
from control_monitor import NaiveSingleTurnMonitor, DeterministicMRPControlMonitor
from benchmark_scenarios import get_benchmark_scenarios


class TestMRPControlArena(unittest.TestCase):
    def test_baseline_mrp_explosion_has_no_frozen_stockouts(self) -> None:
        engine = DeterministicMRPEngine()
        orders, stockouts = engine.run_mrp_explosion()
        self.assertTrue(len(orders) > 0)
        for sku, weeks in stockouts.items():
            self.assertEqual(weeks, [], f"Unexpected baseline stockout on {sku}")

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
                # Deterministic invariant + counterfactual monitor catches all 4
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
