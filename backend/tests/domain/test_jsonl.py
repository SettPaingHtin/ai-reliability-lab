from app.domain.jsonl import MAX_LINES, CaseSpec, dump_jsonl, parse_jsonl


def test_valid_document_with_blank_lines():
    text = '{"input": "a", "expected": "b"}\n\n{"input": "c", "rules": [{"type": "contains", "value": "d"}]}\n'
    result = parse_jsonl(text)
    assert result.ok and len(result.cases) == 2
    assert result.cases[0].expected == "b"
    assert result.cases[1].rules[0]["type"] == "contains"


def test_collects_all_line_errors_with_line_numbers():
    text = "\n".join(
        [
            '{"input": "ok", "expected": "x"}',
            "not json",
            '{"expected": "missing input"}',
            '{"input": "a", "expected": "b", "extra": 1}',
            '{"input": "a"}',
            '{"input": "a", "rules": [{"type": "regex", "value": "("}]}',
            '{"input": "a", "rules": [{"type": "exact"}]}',
            "[1, 2]",
        ]
    )
    result = parse_jsonl(text)
    assert [e.line for e in result.errors] == [2, 3, 4, 5, 6, 7, 8]
    assert "invalid JSON" in result.errors[0].message
    assert "input" in result.errors[1].message
    assert "unknown fields" in result.errors[2].message
    assert "expected" in result.errors[3].message
    assert "invalid rule" in result.errors[4].message
    assert "requires 'expected'" in result.errors[5].message
    assert "JSON object" in result.errors[6].message
    assert len(result.cases) == 1  # the one valid line; caller decides all-or-nothing


def test_type_checks():
    bad = parse_jsonl('{"input": 5, "expected": "x"}\n{"input": "a", "expected": 3}\n{"input": "a", "expected": "b", "metadata": []}')
    assert len(bad.errors) == 3


def test_empty_document_is_an_error():
    assert not parse_jsonl("").ok
    assert not parse_jsonl("\n\n").ok


def test_line_limit():
    result = parse_jsonl("\n".join(['{"input":"a","expected":"b"}'] * (MAX_LINES + 1)))
    assert not result.ok and "too many lines" in result.errors[0].message


def test_error_list_is_capped():
    result = parse_jsonl("\n".join(["bad"] * 200), max_errors=10)
    assert len(result.errors) == 10


def test_round_trip():
    text = '{"input": "q", "expected": "a", "context": "c", "rules": [{"type": "contains", "value": "a", "case_sensitive": false}], "metadata": {"k": 1}}\n'
    first = parse_jsonl(text)
    again = parse_jsonl(dump_jsonl(first.cases))
    assert again.ok and again.cases == first.cases


def test_dump_unicode_and_empty():
    assert "é" in dump_jsonl([CaseSpec(input="é", expected="x")])
    assert dump_jsonl([]) == ""
