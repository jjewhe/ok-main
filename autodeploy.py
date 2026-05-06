import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class AutoDeployHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0
        self.cooldown = 10  # Wait 10 seconds between pushes to avoid spamming GitHub/Railway

    def on_any_event(self, event):
        if event.is_directory or '.git' in event.src_path or '__pycache__' in event.src_path:
            return
            
        current_time = time.time()
        if current_time - self.last_run > self.cooldown:
            print(f"\n[!] Change detected in: {event.src_path}")
            print("[*] Pushing to GitHub to trigger Railway deployment...")
            self.last_run = current_time
            
            try:
                subprocess.run(["git", "add", "."], check=True)
                # If there are no changes, commit will fail, which is fine
                commit_res = subprocess.run(["git", "commit", "-m", f"Auto-deploy: Update {event.src_path.split(chr(92))[-1]}"], capture_output=True)
                if commit_res.returncode == 0:
                    subprocess.run(["git", "push", "origin", "main"], check=True)
                    print("[+] Push successful! Railway is deploying now.")
                else:
                    print("[-] No actual changes to commit.")
            except subprocess.CalledProcessError as e:
                print(f"[!] Git push failed: {e}")

if __name__ == "__main__":
    path = "."
    event_handler = AutoDeployHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    
    print("[*] MRL WARE Auto-Deploy Service is RUNNING.")
    print("[*] Listening for file changes... (Press Ctrl+C to stop)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
