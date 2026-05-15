import io
from PIL import Image
from server.render import render_sentence


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


def test_returns_png_bytes():
    out = render_sentence("שלום עולם")
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_is_800_by_480():
    img = _decode(render_sentence("שלום עולם"))
    assert img.size == (800, 480)


def test_image_is_1_bit_mode():
    img = _decode(render_sentence("שלום עולם"))
    assert img.mode == "1"


def test_short_sentence_renders_some_text():
    img = _decode(render_sentence("שלום"))
    extrema = img.convert("L").getextrema()
    assert extrema == (0, 255), "expected both black and white pixels"


def test_very_long_sentence_still_fits_in_frame():
    long = " ".join(["מילה"] * 80)
    img = _decode(render_sentence(long))
    assert img.size == (800, 480)
    extrema = img.convert("L").getextrema()
    assert extrema == (0, 255)


def test_nikud_text_renders():
    # Sentence with full nikud (matches the format in sentences.md).
    text = "תָּמִיד יִהְיוּ טוֹבִים מִמָּךְ"
    img = _decode(render_sentence(text))
    assert img.size == (800, 480)
    extrema = img.convert("L").getextrema()
    assert extrema == (0, 255)
