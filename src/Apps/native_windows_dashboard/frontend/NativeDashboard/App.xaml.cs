using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using NativeDashboard.Services;

namespace NativeDashboard;

public partial class App : System.Windows.Application
{
    private System.Windows.Forms.NotifyIcon? _tray;
    private MainWindow? _window;
    private BackendProcessManager? _backend;
    private HwndSource? _source;

    private const int HotkeyId = 0x3923;
    private const int WM_HOTKEY = 0x0312;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        try
        {
            var root = ResolveAppRoot();
            _backend = new BackendProcessManager();
            if (!_backend.Start(root, out var backendError))
            {
                System.Windows.MessageBox.Show(
                    "Backend service failed to start.\n\n" +
                    $"{backendError}\n\n" +
                    "Install backend dependencies and run again:\n" +
                    "python -m pip install -r src/Apps/native_windows_dashboard/backend/requirements.txt",
                    "Arctis Native Dashboard",
                    System.Windows.MessageBoxButton.OK,
                    System.Windows.MessageBoxImage.Warning
                );
            }

            _window = new MainWindow(_backend.BackendUrl);
            _window.Hide();
            _window.Deactivated += (_, _) => HideWindowOnSameMonitorClick();

            _tray = new System.Windows.Forms.NotifyIcon
            {
                Text = "Arctis Native Dashboard",
                Visible = true,
                Icon = System.Drawing.SystemIcons.Application,
                ContextMenuStrip = BuildTrayMenu(),
            };
            _tray.MouseClick += (_, args) =>
            {
                if (args.Button == System.Windows.Forms.MouseButtons.Left)
                {
                    ShowWindow();
                }
            };

            RegisterGlobalHotkey();
        }
        catch (Exception ex)
        {
            System.Windows.MessageBox.Show(
                $"Startup failed:\n{ex.Message}",
                "Arctis Native Dashboard",
                System.Windows.MessageBoxButton.OK,
                System.Windows.MessageBoxImage.Error
            );
            Shutdown(-1);
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        try
        {
            if (_source is not null)
            {
                _source.RemoveHook(WndProc);
                UnregisterHotKey(_source.Handle, HotkeyId);
            }
        }
        catch
        {
            // ignore
        }

        if (_tray is not null)
        {
            _tray.Visible = false;
            _tray.Dispose();
        }
        _backend?.Dispose();
        base.OnExit(e);
    }

    private System.Windows.Forms.ContextMenuStrip BuildTrayMenu()
    {
        var menu = new System.Windows.Forms.ContextMenuStrip();
        menu.Items.Add("Open", null, (_, _) => ShowWindow());
        menu.Items.Add("Quit", null, (_, _) => Shutdown());
        return menu;
    }

    private void ShowWindow()
    {
        _window?.ShowNearBottomRight();
    }

    private void HideWindowOnSameMonitorClick()
    {
        if (_window is null || !_window.IsVisible) return;

        var cursor = System.Windows.Forms.Cursor.Position;
        var cursorScreen = System.Windows.Forms.Screen.FromPoint(cursor);
        var windowScreen = System.Windows.Forms.Screen.FromHandle(new WindowInteropHelper(_window).Handle);
        if (cursorScreen.DeviceName == windowScreen.DeviceName)
        {
            _window.Hide();
        }
    }

    private void RegisterGlobalHotkey()
    {
        // Use a message-only HWND so no extra visible window is created.
        var paramsWindow = new HwndSourceParameters("NativeDashboardHotkeySink")
        {
            ParentWindow = new IntPtr(-3), // HWND_MESSAGE
            Width = 0,
            Height = 0,
            PositionX = -32000,
            PositionY = -32000,
            WindowStyle = 0,
        };
        _source = new HwndSource(paramsWindow);
        _source.AddHook(WndProc);

        const uint MOD_CONTROL = 0x0002;
        const uint MOD_ALT = 0x0001;
        const uint VK_F10 = 0x79;
        RegisterHotKey(_source.Handle, HotkeyId, MOD_CONTROL | MOD_ALT, VK_F10);
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == WM_HOTKEY && wParam.ToInt32() == HotkeyId)
        {
            ShowWindow();
            handled = true;
        }
        return IntPtr.Zero;
    }

    private static string ResolveAppRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            var localAppRoot = Path.Combine(current.FullName, "backend");
            if (Directory.Exists(localAppRoot))
            {
                return current.FullName;
            }

            var repoStyleAppRoot = Path.Combine(current.FullName, "src", "Apps", "native_windows_dashboard", "backend");
            if (Directory.Exists(repoStyleAppRoot))
            {
                return Path.Combine(current.FullName, "src", "Apps", "native_windows_dashboard");
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException(
            "Could not find native dashboard app root. Expected a folder containing 'backend'."
        );
    }

    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);
}
