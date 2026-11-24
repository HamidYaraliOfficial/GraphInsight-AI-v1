"""A tiny stand-in for the `streamlit` and `plotly` packages so the dashboard code paths can be smoke-tested
without a browser (used only when the real packages are not installed)."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


class _State(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc

    def __setattr__(self, k, v):
        self[k] = v


class _Bar:
    def progress(self, *a, **k):
        return None

    def empty(self):
        return None


class _Ctx:
    """Context manager that also exposes the streamlit API (columns / tabs / expanders / sidebar)."""

    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self._st

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(self._st, name)


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = _State()
        self.sidebar = _Ctx(self)
        self.calls: list[str] = []

    # layout -------------------------------------------------------------
    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx(self) for _ in range(n)]

    def tabs(self, labels):
        return [_Ctx(self) for _ in labels]

    def expander(self, *a, **k):
        return _Ctx(self)

    def container(self, *a, **k):
        return _Ctx(self)

    def empty(self):
        return _Bar()

    # inputs -------------------------------------------------------------
    def button(self, *a, **k):
        return False

    def download_button(self, *a, **k):
        return False

    def checkbox(self, label, value=False, **k):
        return value

    def toggle(self, label, value=False, **k):
        return value

    def text_input(self, label, value="", **k):
        return value

    def text_area(self, label, value="", **k):
        return value

    def number_input(self, label, min_value=None, max_value=None, value=None, step=None, **k):
        if value is not None:
            return value
        return min_value if min_value is not None else 0.0

    def slider(self, label, min_value=0, max_value=1, value=None, step=None, **k):
        return value if value is not None else min_value

    def selectbox(self, label, options, index=0, **k):
        options = list(options)
        return options[index] if options else None

    def radio(self, label, options, index=0, **k):
        options = list(options)
        return options[index] if options else None

    def multiselect(self, label, options, default=None, **k):
        return list(default) if default is not None else []

    def color_picker(self, label, value="#000000", **k):
        return value

    def file_uploader(self, label, type=None, accept_multiple_files=False, **k):
        return [] if accept_multiple_files else None

    def data_editor(self, df, **k):
        return df

    def progress(self, *a, **k):
        return _Bar()

    # output ---------------------------------------------------------------
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def f(*a, **k):
            self.calls.append(name)
            return None
        return f


def install():
    """Install fake `streamlit` (and a MagicMock `plotly`) into sys.modules; return the fake streamlit."""
    fake = FakeStreamlit()
    sys.modules["streamlit"] = fake
    pl = MagicMock()
    sys.modules.setdefault("plotly", pl)
    sys.modules.setdefault("plotly.graph_objects", pl.graph_objects)
    sys.modules.setdefault("plotly.subplots", pl.subplots)
    return fake
