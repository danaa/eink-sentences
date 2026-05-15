"""Flask app — single endpoint returns a Hebrew PNG for the e-paper."""
from __future__ import annotations

import logging
import random

from flask import Flask, Response

from server.render import render_sentence
from server.sentences_source import fetch_sentences

log = logging.getLogger(__name__)

FALLBACK_NO_SENTENCES = "אין משפטים"
FALLBACK_ERROR = "שגיאה"


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def health() -> str:
        return "ok"

    @app.get("/image.png")
    def image() -> Response:
        try:
            sentences = fetch_sentences()
            if not sentences:
                png = render_sentence(FALLBACK_NO_SENTENCES)
            else:
                png = render_sentence(random.choice(sentences))
        except Exception as e:
            log.exception("Render failed: %s", e)
            png = render_sentence(FALLBACK_ERROR)

        return Response(
            png,
            mimetype="image/png",
            headers={"Cache-Control": "no-store"},
        )

    return app


app = create_app()
