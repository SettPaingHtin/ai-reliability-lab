from app.domain.scoring import MAX_PATTERN_CHARS, Rule, RuleValidationError, parse_rule, score_output


def _raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    return False


def test_default_exact_match_passes_and_fails():
    assert score_output("Paris", [], "Paris").passed
    miss = score_output("Lyon", [], "Paris")
    assert not miss.passed and miss.score == 0.0
    assert "Paris" in miss.rule_results[0].message and "Lyon" in miss.rule_results[0].message


def test_exact_strip_and_case_options():
    assert score_output("  paris \n", [Rule("exact", "Paris", case_sensitive=False)], None).passed
    assert not score_output(" Paris", [Rule("exact", "Paris", strip=False)], None).passed
    assert not score_output("paris", [Rule("exact", "Paris")], None).passed


def test_contains_and_not_contains():
    assert score_output("The capital is Paris.", [Rule("contains", "Paris")], None).passed
    assert not score_output("Rome", [Rule("contains", "Paris")], None).passed
    assert score_output("safe text", [Rule("not_contains", "secret")], None).passed
    assert not score_output("has secret", [Rule("not_contains", "secret")], None).passed


def test_regex_rule():
    assert score_output("Order #1234 ok", [Rule("regex", r"#\d{4}")], None).passed
    assert not score_output("Order ok", [Rule("regex", r"#\d{4}")], None).passed
    assert score_output("ABC", [Rule("regex", "abc", case_sensitive=False)], None).passed


def test_multiple_rules_all_must_pass_and_score_is_mean():
    rules = [Rule("contains", "a"), Rule("contains", "z")]
    result = score_output("abc", rules, None)
    assert not result.passed
    assert result.score == 0.5
    assert [r.passed for r in result.rule_results] == [True, False]


def test_details_are_labelled_deterministic():
    assert score_output("x", [], "x").to_dict()["kind"] == "deterministic"


def test_no_rules_and_no_expected_is_an_error():
    assert _raises(ValueError, score_output, "x", [], None)


def test_exact_rule_without_any_target_fails_safely():
    result = score_output("x", [Rule("exact")], None)
    assert not result.passed


def test_parse_rule_validation():
    assert parse_rule({"type": "contains", "value": "x"}).value == "x"
    assert _raises(RuleValidationError, parse_rule, "nope")
    assert _raises(RuleValidationError, parse_rule, {"type": "fuzzy"})
    assert _raises(RuleValidationError, parse_rule, {"type": "contains"})
    assert _raises(RuleValidationError, parse_rule, {"type": "exact", "bogus": 1})
    assert _raises(RuleValidationError, parse_rule, {"type": "exact", "strip": "yes"})
    assert _raises(RuleValidationError, parse_rule, {"type": "regex", "value": "("})
    assert _raises(RuleValidationError, parse_rule, {"type": "regex", "value": "a" * (MAX_PATTERN_CHARS + 1)})


def test_oversized_output_is_bounded_before_matching():
    huge = "a" * 100_000 + "NEEDLE"
    assert not score_output(huge, [Rule("contains", "NEEDLE")], None).passed
