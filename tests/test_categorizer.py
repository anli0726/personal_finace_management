from backend.statements.categorizer import (
    CategorizationResult,
    CategorizerPipeline,
    RuleBasedCategorizer,
)


def test_rule_based_matches_groceries_keyword():
    categorizer = RuleBasedCategorizer()

    result = categorizer.categorize(description="Walmart Supercenter #123", amount=-54.12)

    assert result is not None
    assert result.category == "groceries"
    assert result.source.startswith("rules")
    assert result.confidence > 0.0


def test_pipeline_uses_fallback_when_rules_low_confidence():
    def fake_fallback(description: str, amount: float, merchant=None, mcc=None):
        return CategorizationResult(category="travel", confidence=0.9, source="dummy-fallback")

    # High threshold so the rule result will be considered low confidence
    rule = RuleBasedCategorizer(min_confidence=0.9)
    pipeline = CategorizerPipeline(primary=rule, fallback=fake_fallback, min_confidence_for_rules=0.8)

    result = pipeline.categorize(description="Uber trip", amount=-20.0)

    assert result is not None
    assert result.category == "travel"
    assert result.source == "dummy-fallback"
