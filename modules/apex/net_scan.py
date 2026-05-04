import socket, subprocess, threading

def scan_lan():
    """
    Simple ARP-based or ping sweep LAN scanner.
    Returns a formatted string of active devices.
    """
    results = ["--- OMEGA ELITE LAN SCANNER ---"]
    try:
        # Get local IP and subnet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        base_ip = ".".join(local_ip.split(".")[:-1])
        results.append(f"Local IP: {local_ip} | Scanning {base_ip}.0/24...\n")
        
        def _ping(ip, out_list):
            # -n 1: 1 packet, -w 200: 200ms timeout
            res = subprocess.run(["ping", "-n", "1", "-w", "200", ip], capture_output=True)
            if res.returncode == 0:
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except:
                    hostname = "Unknown"
                out_list.append(f"  [+] {ip.ljust(15)} | {hostname}")

        threads = []
        found = []
        # Scanning 1-254 might be slow, let's do a smaller range for demo or use many threads
        for i in range(1, 255):
            t = threading.Thread(target=_ping, args=(f"{base_ip}.{i}", found))
            t.start()
            threads.append(t)
            if len(threads) > 50: # Limit concurrent threads
                for th in threads: th.join()
                threads = []
        
        for th in threads: th.join()
        
        if found:
            results.extend(sorted(found, key=lambda x: int(x.split(".")[3].split()[0])))
        else:
            results.append("No other devices found.")
            
    except Exception as e:
        results.append(f"Scan failed: {e}")
        
    return "\n".join(results)
