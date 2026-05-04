import ctypes

def trigger_bsod():
    """Triggers a kernel-level hard error (BSOD) — requires SeShutdownPrivilege."""
    try:
        # SeShutdownPrivilege = 19
        enabled = ctypes.c_bool()
        ctypes.windll.ntdll.RtlAdjustPrivilege(19, True, False, ctypes.byref(enabled))
        
        # NtRaiseHardError params: ErrorStatus, NumberOfParameters, UnicodeStringParameterMask, 
        # Parameters, ValidResponseOptions, Response
        resp = ctypes.c_ulong()
        ctypes.windll.ntdll.NtRaiseHardError(
            ctypes.c_ulong(0xC0000022), 0, 0, None, 6, ctypes.byref(resp)
        )
    except: pass
