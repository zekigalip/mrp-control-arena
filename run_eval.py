"""
CLI Evaluation Runner for MRP-Control-Arena.

Compares Naive Single-Turn Tool Monitoring against Deterministic MRP Invariant &
Provenance Control across the benchmark suite.
"""

from __future__ import annotations
from mrp_engine import DeterministicMRPEngine
from control_monitor import NaiveSingleTurnMonitor, DeterministicMRPControlMonitor
from benchmark_scenarios import get_benchmark_scenarios


def run_evaluation() -> None:
    scenarios = get_benchmark_scenarios()
    naive_monitor = NaiveSingleTurnMonitor()
    control_monitor = DeterministicMRPControlMonitor()

    print("=" * 92)
    print("MRP-CONTROL-ARENA: EMPIRICAL EVALUATION OF AI CONTROL IN DETERMINISTIC ERP/EDI SYSTEMS")
    print("=" * 92)
    print(
        f"{'ID':<9} | {'Category':<11} | {'Naive Monitor':<15} | {'MRP-Control':<15} | {'Cost Delta':<11} | {'Primary Invariant Triggered'}"
    )
    print("-" * 92)

    naive_caught = 0
    control_caught = 0
    adversarial_count = 0
    benign_count = 0
    control_false_positives = 0
    prevented_loss_usd = 0.0

    for scen in scenarios:
        engine = DeterministicMRPEngine()
        naive_res = naive_monitor.evaluate_batch(engine, scen.tool_calls)
        ctrl_res = control_monitor.evaluate_batch(engine, scen.tool_calls)

        naive_status = "ALLOWED" if naive_res.allowed else "BLOCKED"
        ctrl_status = "ALLOWED" if ctrl_res.allowed else "BLOCKED"
        primary_inv = ctrl_res.triggered_invariants[0].split(":")[0] if ctrl_res.triggered_invariants else "None (Safe)"

        if scen.category == "adversarial":
            adversarial_count += 1
            if not naive_res.allowed:
                naive_caught += 1
            if not ctrl_res.allowed:
                control_caught += 1
                prevented_loss_usd += scen.estimated_financial_impact_usd
        else:
            benign_count += 1
            if not ctrl_res.allowed:
                control_false_positives += 1

        print(
            f"{scen.scenario_id:<9} | {scen.category:<11} | {naive_status:<15} | {ctrl_status:<15} | "
            f"{ctrl_res.total_order_cost_delta_pct:>+9.1f}% | {primary_inv}"
        )

    print("-" * 92)
    print(f"Adversarial Sabotage Catch Rate (Naive Single-Turn Monitor): {naive_caught}/{adversarial_count} ({naive_caught/adversarial_count*100:.0f}%)")
    print(f"Adversarial Sabotage Catch Rate (Deterministic MRP-Control): {control_caught}/{adversarial_count} ({control_caught/adversarial_count*100:.0f}%)")
    print(f"Benign Operational False-Positive Rate (MRP-Control):        {control_false_positives}/{benign_count} ({control_false_positives/benign_count*100:.0f}%)")
    print(f"Total Simulated Line-Stoppage & Bullwhip Loss Prevented:     ${prevented_loss_usd:,.0f} USD")
    print("=" * 92)


if __name__ == "__main__":
    run_evaluation()
