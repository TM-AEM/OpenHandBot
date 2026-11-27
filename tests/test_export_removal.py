"""OHB2-REMOVE-EXPORT: the export button and export feature are permanently gone."""
from __future__ import annotations

import inspect
from pathlib import Path

import bot.handlers as handlers
import bot.keyboards as keyboards
import bot.openhands_client as openhands_client
import bot.web.services as web_services
from bot import features

STATIC = Path(__file__).resolve().parents[1] / "bot" / "web" / "static"
EXPLANATORY_TEXT = "بيبعتلك الرد جوه code block"


def test_export_entry_points_are_removed():
    assert not hasattr(handlers, "export_conversation")
    assert not hasattr(openhands_client.OpenHandsClient, "export_conversation")
    assert not hasattr(web_services.MiniAppService, "conversation_export")
    assert not hasattr(web_services, "export_filename")
    assert not hasattr(openhands_client, "MAX_EXPORT_BYTES")


def test_export_is_not_a_feature_flag():
    assert "export" not in features.HIDDEN_FEATURES


def test_keyboard_has_no_export_button():
    callbacks = [
        button.callback_data
        for row in keyboards.conversation_actions("c1").inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert not any(cb.startswith("export:") for cb in callbacks)
    labels = [
        button.text
        for row in keyboards.conversation_actions("c1").inline_keyboard
        for button in row
    ]
    assert not any("تصدير" in label for label in labels)


def test_explanatory_copy_is_removed():
    source = inspect.getsource(handlers._open_conversation_view)
    assert EXPLANATORY_TEXT not in source


def test_frontend_has_no_export_surface():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "export.js" not in index
    assert "RecovoExport" not in app_js
    assert "/export" not in app_js
    assert not (STATIC / "export.js").exists()
