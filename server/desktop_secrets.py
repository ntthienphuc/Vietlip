"""Windows current-user DPAPI and atomic companion-file writes."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import tempfile


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.c_void_p)]


def _windows_protect(data, *, decrypt=False):
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buf = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buf, ctypes.c_void_p))
    result = _Blob()
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


def _folder():
    return Path(os.environ["LOCALAPPDATA"]) / "VietLip"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        name = Path(temp.name)
        try:
            temp.write(data)
            temp.close()
            os.replace(name, path)
        finally:
            temp.close()
            name.unlink(missing_ok=True)
