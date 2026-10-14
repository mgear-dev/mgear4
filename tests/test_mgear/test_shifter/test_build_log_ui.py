"""Shifter build log window tests"""

import time


def test_search_filters_once_typing_pauses(clean_settings, monkeypatch):
    """Typing a search term re-renders the log once, not per key."""
    from mgear.vendor.Qt import QtWidgets
    from mgear.shifter.build_log import ui

    calls = []
    original = ui.BuildLogWindow._apply_filters

    def counting(self):
        calls.append(self._search_text)
        original(self)

    monkeypatch.setattr(ui.BuildLogWindow, "_apply_filters", counting)
    monkeypatch.setattr(ui.BuildLogWindow, "SEARCH_DELAY", 10)
    window = ui.BuildLogWindow()
    try:
        del calls[:]
        for size in range(1, 6):
            window.search_input.setText("joint"[:size])
        assert calls == []

        deadline = time.time() + 2.0
        while not calls and time.time() < deadline:
            QtWidgets.QApplication.processEvents()
            time.sleep(0.005)
        assert calls == ["joint"]
    finally:
        window.close()
