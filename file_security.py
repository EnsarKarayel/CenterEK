"""Restrict generated secrets to the creating user, SYSTEM and local admins."""
import os
from pathlib import Path
import re
import subprocess
import ctypes


def restrict(path, directory=False):
    path = Path(path)
    if os.name != 'nt':
        path.chmod(0o700 if directory else 0o600)
        return
    identity = subprocess.check_output([str(Path(os.environ['WINDIR']) / 'System32/whoami.exe'), '/user', '/fo', 'csv', '/nh'], timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    match = re.search(rb'S-1-\d+(?:-\d+)+', identity)
    if not match:
        raise PermissionError('Mevcut Windows kullanıcı SID değeri okunamadı')
    principals = [match[0].decode('ascii'), 'S-1-5-18', 'S-1-5-32-544']
    # Replace the complete DACL. /grant:r alone leaves unrelated explicit ACEs
    # in place, which is unsafe for a pre-created backup/key folder.
    from ctypes import wintypes
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    pointer = ctypes.c_void_p
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(pointer), ctypes.POINTER(wintypes.DWORD)]
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    api.GetSecurityDescriptorDacl.argtypes = [pointer, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(pointer), ctypes.POINTER(wintypes.BOOL)]
    api.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    api.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, pointer, pointer, pointer, pointer]
    api.SetNamedSecurityInfoW.restype = wintypes.DWORD
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    flags = 'OICI' if directory else ''
    sddl = 'D:P' + ''.join('(A;' + flags + ';FA;;;' + sid + ')' for sid in dict.fromkeys(principals))
    descriptor = pointer()
    if not api.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
        raise PermissionError('Gizli dosya güvenlik tanımı oluşturulamadı')
    try:
        present, defaulted, dacl = wintypes.BOOL(), wintypes.BOOL(), pointer()
        if not api.GetSecurityDescriptorDacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) or not present or not dacl:
            raise PermissionError('Gizli dosya erişim listesi oluşturulamadı')
        code = api.SetNamedSecurityInfoW(str(path.resolve()), 1, 0x80000004, None, None, dacl, None)
        if code:
            raise PermissionError(code, 'Gizli dosya izinleri uygulanamadı')
    finally:
        kernel.LocalFree(descriptor)
