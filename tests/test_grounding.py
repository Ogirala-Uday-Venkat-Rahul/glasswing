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


def test_operands_from_the_question_count_as_supported():
    # The calculator false positive: the answer echoes the numbers the user
    # asked about, but the tool result only carries the computed total. The
    # operands are grounded by the question, so nothing should be flagged.
    answer = "4823 * 197 = 950,131"
    evidence = "950131"  # what the calculator returned
    asked = "What is 4823 * 197?"
    assert ground_answer(answer, evidence, asked=asked) == answer


def test_still_flags_a_number_in_neither_question_nor_evidence():
    # Widening evidence to the question must not blunt the real catch: a figure
    # the model invented (not asked, not in results) is still flagged.
    answer = "The MacBook Air is $1,099."
    evidence = "MacBook Air From $1299 at the Apple Store"
    asked = "What is the price of the MacBook Air M3?"
    out = ground_answer(answer, evidence, asked=asked)
    assert "couldn't confirm" in out
    assert "1,099" in out


def test_accepts_a_rounded_number():
    # The model rounds 62.14 to "about 62". That is the actual rounding of the
    # source number, so it must not be flagged.
    answer = "It's about 62 miles."
    evidence = "62.14"
    assert ground_answer(answer, evidence, asked="100 km in miles?") == answer


def test_accepts_rounding_to_one_decimal():
    answer = "Roughly 62.1 miles."
    evidence = "62.14 miles"
    assert ground_answer(answer, evidence, asked="convert it") == answer


def test_rounding_does_not_accept_a_close_but_wrong_number():
    # 1199 is near 1299 but is not a rounding of it, so it stays flagged. This is
    # the line between harmless rounding and a genuinely wrong figure.
    answer = "The price is $1,199."
    evidence = "listed From $1,299"
    out = ground_answer(answer, evidence, asked="price?")
    assert "couldn't confirm" in out


def test_expands_magnitude_words():
    # "$1.2 million" must match the plain 1200000 a tool returned.
    answer = "Revenue was $1.2 million."
    evidence = "annual revenue 1200000 usd"
    assert ground_answer(answer, evidence, asked="revenue?") == answer
