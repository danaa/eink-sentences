import re

_LINE_NUMBER_PREFIX = re.compile(r"^\d+\t")
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")


def parse_sentences(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        line = _LINE_NUMBER_PREFIX.sub("", line).strip()
        if not line:
            continue
        line = _MARKDOWN_BOLD.sub(r"\1", line)
        if line:
            out.append(line)
    return out
