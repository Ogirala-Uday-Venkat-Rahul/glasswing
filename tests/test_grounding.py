from agent.grounding import ground_answer


def test_flags_number_absent_from_evidence():
    # The exact bug we saw: model states $1,099, sources only support $1299.
    answer = "The MacBook Air is $1,099."
    evidence = "MacBook Air From $1299 at the Apple Store"
    out = ground_answer(answer, evidence)
    assert "couldn't confirm" in out
    assert "1,099" in out


def test_passes_number_present_in_evidence():
    answer = "The MacBook Air is $1,299."
    evidence = "MacBook Air From $1299 at the Apple Store"
    assert ground_answer(answer, evidence) == answer


def test_comma_and_decimal_forms_match():
    # 1,299 in the answer must count as supported by 1299.00 in the evidence.
    answer = "It costs 1,299."
    evidence = "listed at 1299.00 dollars"
    assert ground_answer(answer, evidence) == answer


def test_single_digits_are_ignored():
    # "M3" / "13-inch" style small numbers must not trigger false alarms.
    answer = "The M3 chip powers it."
    evidence = "Apple silicon laptop"
    assert ground_answer(answer, evidence) == answer


def test_no_evidence_means_no_flagging():
    # With no tool results there is nothing to verify against, so leave it alone.
    answer = "That would be about $500."
    assert ground_answer(answer, "") == answer
