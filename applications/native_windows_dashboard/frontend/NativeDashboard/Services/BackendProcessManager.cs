using System.Diagnostics;
using System.IO;

namespace NativeDashboard.Services;

public sealed class BackendProcessManager : IDisposable
{
    private Process? _process;
    public string BackendUrl { get; } = "http://127.0.0.1:59231";

    public bool Start(string workingDirectory, out string? error)
    {
        error = null;
        if (_process is { HasExited: false })
        {
            return true;
        }

        var backendDir = Path.Combine(workingDirectory, "backend");
        if (!Directory.Exists(backendDir))
        {
            error = $"Backend folder was not found: {backendDir}";
            return false;
        }

        var repoRoot = Path.GetFullPath(Path.Combine(workingDirectory, "..", ".."));
        var candidatePython = new[]
        {
            Path.Combine(repoRoot, ".venv", "Scripts", "python.exe"),
            Path.Combine(workingDirectory, ".venv", "Scripts", "python.exe"),
            "python",
            "py",
        };

        foreach (var candidate in candidatePython)
        {
            var args = string.Equals(candidate, "py", StringComparison.OrdinalIgnoreCase) ? "-3 main.py" : "main.py";
            var psi = new ProcessStartInfo
            {
                FileName = candidate,
                Arguments = args,
                WorkingDirectory = backendDir,
                UseShellExecute = false,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                CreateNoWindow = true,
            };

            try
            {
                _process = Process.Start(psi);
                if (_process is null)
                {
                    continue;
                }

                if (_process.WaitForExit(1200))
                {
                    var stderr = _process.StandardError.ReadToEnd();
                    var stdout = _process.StandardOutput.ReadToEnd();
                    error = $"Backend exited immediately when launched via '{candidate}'.\n{stderr}\n{stdout}".Trim();
                    _process.Dispose();
                    _process = null;
                    continue;
                }

                return true;
            }
            catch (Exception ex)
            {
                error = $"Failed to start backend via '{candidate}': {ex.Message}";
            }
        }

        return false;
    }

    public void Stop()
    {
        try
        {
            if (_process is { HasExited: false })
            {
                _process.Kill(entireProcessTree: true);
                _process.WaitForExit(1500);
            }
        }
        catch
        {
            // ignore shutdown failures
        }
    }

    public void Dispose()
    {
        Stop();
    }
}
