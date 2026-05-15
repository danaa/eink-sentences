from server.parser import parse_sentences


def test_strips_leading_line_numbers():
    raw = "1\tתמיד יהיו טובים\n2\t\n3\tאני לומדת\n"
    assert parse_sentences(raw) == ["תמיד יהיו טובים", "אני לומדת"]


def test_strips_markdown_bold():
    raw = "**הרגישות שלך היא כוח אדיר**"
    assert parse_sentences(raw) == ["הרגישות שלך היא כוח אדיר"]


def test_skips_blank_and_whitespace_only_lines():
    raw = "שלום\n\n   \nעולם\n"
    assert parse_sentences(raw) == ["שלום", "עולם"]


def test_handles_plain_lines_with_no_prefix():
    raw = "שורה ראשונה\nשורה שנייה\n"
    assert parse_sentences(raw) == ["שורה ראשונה", "שורה שנייה"]


def test_returns_empty_list_for_empty_input():
    assert parse_sentences("") == []
    assert parse_sentences("\n\n\n") == []
