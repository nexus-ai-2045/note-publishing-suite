"""配布元の実ファイルを一つのprivate namespaceで読み込む。"""
from __future__ import annotations

import _imp
import hashlib
import importlib.util
import re
import sys
import threading
from pathlib import Path
from types import ModuleType

_SOURCE = Path(__file__).resolve()
_KEY = "_nps_loader_" + hashlib.sha256(str(_SOURCE).encode()).hexdigest()


def _same_source(module: ModuleType, path: Path) -> bool:
    return bool(getattr(module, "__file__", None)) and Path(module.__file__).resolve() == path


def _canonical_loader() -> ModuleType:
    _imp.acquire_lock()
    try:
        existing = sys.modules.get(_KEY)
        if existing is not None:
            api = getattr(existing, "load_script", None)
            code = getattr(api, "__code__", None)
            if not _same_source(existing, _SOURCE) or code is None or Path(code.co_filename).resolve() != _SOURCE:
                raise ImportError("NPS loader cache source mismatch")
            return existing
        spec = importlib.util.spec_from_file_location(_KEY, _SOURCE)
        if spec is None or spec.loader is None:
            raise ImportError("cannot load NPS loader")
        module = importlib.util.module_from_spec(spec)
        sys.modules[_KEY] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            if sys.modules.get(_KEY) is module:
                del sys.modules[_KEY]
            raise
        return module
    finally:
        _imp.release_lock()


_LOCK = threading.RLock()
_LOADING: set[str] = set()
_MODULES: dict[str, ModuleType] = {}


def load_script(name: str) -> ModuleType:
    """basenameを同配布元へ束縛する。公開module cacheとsys.pathは変更しない。"""
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None or name == "nps_script_loader":
        raise ImportError("unsupported NPS script name")
    path = _SOURCE.with_name(name + ".py")
    if not path.is_file() or path.resolve().parent != _SOURCE.parent:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)
    path = path.resolve()
    key = "_nps_script_" + hashlib.sha256(str(path).encode()).hexdigest()
    with _LOCK:
        if key in _LOADING:
            raise ImportError("NPS circular initialization must be deferred: " + name)
        existing = sys.modules.get(key)
        if existing is not None:
            if existing is not _MODULES.get(key) or not _same_source(existing, path):
                raise ImportError("NPS script cache source mismatch")
            return existing
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise ImportError("cannot load NPS sibling source")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        _LOADING.add(key)
        try:
            spec.loader.exec_module(module)
        except BaseException:
            if sys.modules.get(key) is module:
                del sys.modules[key]
            raise
        finally:
            _LOADING.remove(key)
        _MODULES[key] = module
        return module


if __name__ != _KEY:
    load_script = _canonical_loader().load_script
