from safety_graph_orchestrator.evals.benchmark import SafetyEvalsHarness


def test_safety_evals_benchmark():
    harness = SafetyEvalsHarness()
    results = harness.run_benchmark()

    assert results.total_scenarios == 4
    assert results.zero_false_negative_rate == 100.0
    assert results.regulatory_rule_recall == 100.0
    assert results.blame_free_systemic_score == 100.0
    assert results.passed_scenarios == 4
