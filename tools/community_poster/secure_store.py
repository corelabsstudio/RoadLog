"""
비밀번호 로컬 보호 저장.

Windows: DPAPI (사용자 계정 묶임)
기타: 기기 식별자 기반 XOR+HMAC (평문보다는 낫지만 DPAPI만 큼 강하지 않음)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys
from pathlib import Path

_PREFIX_DPAPI = "dpapi:"
_PREFIX_XOR = "xor1:"


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _fallback_key() -> bytes:
    material = "|".join(
        [
            os.environ.get("USERNAME", ""),
            os.environ.get("USER", ""),
            os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "")),
            "promoroutine-v1-salt",
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def _dpapi_protect(raw: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        blob_in = DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            "ReachKit",
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            return None
        try:
            out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return out
    except Exception:
        return None


def _dpapi_unprotect(raw: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        blob_in = DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            return None
        try:
            out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return out
    except Exception:
        return None


def encrypt_secret(plain: str) -> str:
    """평문 → 저장용 문자열. 빈 문자열은 그대로."""
    if not plain:
        return ""
    raw = plain.encode("utf-8")
    protected = _dpapi_protect(raw)
    if protected is not None:
        return _PREFIX_DPAPI + base64.urlsafe_b64encode(protected).decode("ascii")
    key = _fallback_key()
    xored = _xor_bytes(raw, key)
    tag = hmac.new(key, xored, hashlib.sha256).digest()[:16]
    return _PREFIX_XOR + base64.urlsafe_b64encode(tag + xored).decode("ascii")


def decrypt_secret(token: str) -> str:
    """저장 문자열 → 평문. 예전 평문 저장분도 그대로 반환(마이그레이션)."""
    if not token:
        return ""
    if token.startswith(_PREFIX_DPAPI):
        try:
            raw = base64.urlsafe_b64decode(token[len(_PREFIX_DPAPI) :].encode("ascii"))
            out = _dpapi_unprotect(raw)
            return out.decode("utf-8") if out else ""
        except Exception:
            return ""
    if token.startswith(_PREFIX_XOR):
        try:
            raw = base64.urlsafe_b64decode(token[len(_PREFIX_XOR) :].encode("ascii"))
            key = _fallback_key()
            tag, xored = raw[:16], raw[16:]
            expect = hmac.new(key, xored, hashlib.sha256).digest()[:16]
            if not hmac.compare_digest(tag, expect):
                return ""
            return _xor_bytes(xored, key).decode("utf-8")
        except Exception:
            return ""
    # 레거시 평문
    return token


def migrate_password_field(data: dict) -> dict:
    """last_form.json 로드 시 password 복호화 / 저장 시 암호화용 헬퍼."""
    out = dict(data)
    pw = out.get("password") or ""
    if pw and not (pw.startswith(_PREFIX_DPAPI) or pw.startswith(_PREFIX_XOR)):
        # 평문으로 로드된 상태 유지 (decrypt는 identity)
        pass
    elif pw:
        out["password"] = decrypt_secret(pw)
    return out


def prepare_password_for_save(plain: str, save: bool) -> str:
    if not save or not plain:
        return ""
    return encrypt_secret(plain)
