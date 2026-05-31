from scripts import text_match


def _matches(names, text):
    pat = text_match.build_name_pattern(names)
    return bool(pat and pat.search(text))


def test_latin_word_boundary_preserved():
    assert _matches(["Karpathy"], "per Karpathy's blog")
    assert not _matches(["Karpathy"], "nanocarpathy")


def test_korean_name_plus_josa_matches():
    for text in ["김단테는 갔다", "카르파시가 썼다", "김단테를 봤다",
                 "서울에서 만났다", "단테로 정했다", "단테의 글"]:
        assert _matches(["김단테", "카르파시", "서울", "단테"], text), text


def test_korean_name_in_compound_not_matched():
    assert not _matches(["단테"], "단테나무 아래")   # 나무 is not josa+boundary


def test_korean_name_preceded_by_hangul_not_matched():
    assert not _matches(["단테"], "김단테는 갔다")    # '단테' is inside '김단테'


def test_multiword_korean_name():
    assert _matches(["안드레이 카르파시"], "안드레이 카르파시가 발표했다")


def test_alias_alternation_and_case_insensitive():
    assert _matches(["Andrej Karpathy", "Karpathy"], "met ANDREJ karpathy today")


def test_empty_names_returns_none():
    assert text_match.build_name_pattern([]) is None
    assert text_match.build_name_pattern(["", "  "]) is None


def test_no_redos_on_pathological_input():
    pat = text_match.build_name_pattern(["dante"])
    pat.search("a" * 50000 + "!")  # must return promptly, no catastrophic backtracking
