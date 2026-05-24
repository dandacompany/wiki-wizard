from scripts.slugify import slugify


def test_basic_english():
    assert slugify("Hello World") == "hello-world"


def test_strips_punctuation_and_collapses_spaces():
    assert slugify("  This! is  a TEST.  ") == "this-is-a-test"


def test_preserves_korean_characters():
    assert slugify("한글 메모 제목") == "한글-메모-제목"


def test_handles_mixed_korean_english():
    assert slugify("Karpathy LLM Wiki 정리") == "karpathy-llm-wiki-정리"


def test_truncates_to_max_length():
    long = "a" * 200
    assert len(slugify(long, max_length=80)) <= 80


def test_falls_back_to_default_when_empty():
    assert slugify("!!!", default="untitled") == "untitled"
