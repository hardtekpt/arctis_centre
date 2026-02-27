using System.Runtime.InteropServices;
using System.Net.Http;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Threading;
using NativeDashboard.Models;
using NativeDashboard.Services;

namespace NativeDashboard;

public partial class MainWindow : Window
{
    private static readonly string[] ChannelNames = new[] { "master", "game", "chatRender", "media", "aux", "chatCapture" };

    private readonly BackendApiClient _api;
    private readonly Dictionary<string, ChannelRow> _rows = new();
    private readonly CancellationTokenSource _cts = new();
    private readonly DispatcherTimer _pollTimer;
    private bool _suspendUpdates;
    private bool _refreshInProgress;
    private int _presetTickCounter;
    private string _lastStateRenderKey = "";
    private string _lastPresetsRenderKey = "";

    public MainWindow(string backendUrl)
    {
        InitializeComponent();
        _api = new BackendApiClient(backendUrl);
        BuildRows();
        Loaded += OnLoaded;
        Closed += (_, _) => _cts.Cancel();
        _pollTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(250) };
        _pollTimer.Tick += async (_, _) =>
        {
            if (_refreshInProgress) return;
            _refreshInProgress = true;
            try
            {
                await RefreshAsync();
                _presetTickCounter++;
                if (_presetTickCounter >= 8)
                {
                    _presetTickCounter = 0;
                    await LoadPresetsAsync();
                }
            }
            finally
            {
                _refreshInProgress = false;
            }
        };
    }

    public void ShowNearBottomRight()
    {
        Show();
        Activate();
        BringIntoView();
        MoveToBottomRight();
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        ApplyNativeWindowEffects();
        MoveToBottomRight();
        await LoadPresetsAsync();
        _pollTimer.Start();
    }

    private async Task LoadPresetsAsync()
    {
        try
        {
            var presets = await _api.GetPresetsAsync(_cts.Token);
            var presetsKey = BuildPresetsRenderKey(presets);
            if (presetsKey == _lastPresetsRenderKey)
            {
                return;
            }
            foreach (var kv in presets)
            {
                if (!_rows.TryGetValue(kv.Key, out var row)) continue;
                row.PresetCombo.Items.Clear();
                foreach (var p in kv.Value)
                {
                    row.PresetCombo.Items.Add(new ComboBoxItem { Content = p.name, Tag = p.id });
                }
                if (row.PresetCombo.Items.Count == 0)
                {
                    row.PresetCombo.Items.Add(new ComboBoxItem { Content = "No presets", Tag = "__none__" });
                }
            }
            _lastPresetsRenderKey = presetsKey;
        }
        catch (TaskCanceledException)
        {
            // Backend can be starting up or temporarily busy; keep current UI state.
        }
        catch (HttpRequestException)
        {
            // Transient backend communication issue; keep current UI state.
        }
        catch (Exception ex)
        {
            StatusText.Text = ex.Message;
        }
    }

    private async Task RefreshAsync()
    {
        try
        {
            var state = await _api.GetStateAsync(_cts.Token);
            if (state is null) return;
            var renderKey = BuildStateRenderKey(state);
            if (renderKey == _lastStateRenderKey)
            {
                return;
            }
            ApplyState(state);
            _lastStateRenderKey = renderKey;
        }
        catch (TaskCanceledException)
        {
            StatusText.Text = "waiting for backend...";
        }
        catch (HttpRequestException)
        {
            StatusText.Text = "backend unavailable";
        }
        catch (Exception ex)
        {
            StatusText.Text = ex.Message;
        }
    }

    private void ApplyState(DashboardState state)
    {
        _suspendUpdates = true;
        try
        {
            ConnectionText.Text = $"connected={YN(state.connected)} wireless={YN(state.wireless)} bluetooth={YN(state.bluetooth)}";
            ModesText.Text = $"ANC={state.anc_mode ?? "N/A"} mute={YN(state.mic_mute)} sidetone={state.sidetone_level?.ToString() ?? "N/A"}";
            LiveText.Text =
                $"chat mix={(state.chat_mix_balance?.ToString() ?? "N/A")}% OLED brightness={state.oled_brightness?.ToString() ?? "N/A"}";
            HeadsetBatteryBar.Value = state.headset_battery_percent ?? 0;
            BaseBatteryBar.Value = state.base_battery_percent ?? 0;
            HeadsetBatteryText.Text = PercentOrNA(state.headset_battery_percent);
            BaseBatteryText.Text = PercentOrNA(state.base_battery_percent);
            HeadsetVolumeBar.Value = state.headset_volume_percent ?? 0;
            HeadsetVolumeText.Text = PercentOrNA(state.headset_volume_percent);

            foreach (var channel in ChannelNames)
            {
                if (!_rows.TryGetValue(channel, out var row)) continue;
                if (state.channel_volume is not null && state.channel_volume.TryGetValue(channel, out var vol))
                {
                    row.VolumeSlider.Value = vol;
                    row.VolumeText.Text = $"{vol}%";
                }
                if (state.channel_mute is not null && state.channel_mute.TryGetValue(channel, out var muted))
                {
                    row.MuteCheck.IsChecked = muted;
                }
                if (state.channel_preset is not null && state.channel_preset.TryGetValue(channel, out var presetId))
                {
                    if (presetId is not null)
                    {
                        foreach (ComboBoxItem item in row.PresetCombo.Items)
                        {
                            if (item.Tag?.ToString() == presetId)
                            {
                                row.PresetCombo.SelectedItem = item;
                                break;
                            }
                        }
                    }
                }
                if (state.channel_apps is not null && state.channel_apps.TryGetValue(channel, out var apps))
                {
                    row.AppsText.Text = apps.Count > 0 ? string.Join(", ", apps) : "N/A";
                }
            }

            StatusText.Text = state.status == "running"
                ? $"updated: {state.updated_at ?? "--:--:--"}"
                : $"status: {state.status} {state.last_error}";
        }
        finally
        {
            _suspendUpdates = false;
        }
    }

    private void BuildRows()
    {
        foreach (var channel in ChannelNames)
        {
            var rowBorder = new Border
            {
                CornerRadius = new CornerRadius(10),
                BorderBrush = (System.Windows.Media.Brush)new System.Windows.Media.BrushConverter().ConvertFromString("#33FFFFFF"),
                BorderThickness = new Thickness(1),
                Background = (System.Windows.Media.Brush)new System.Windows.Media.BrushConverter().ConvertFromString("#19000000"),
                Padding = new Thickness(8),
                Margin = new Thickness(0, 0, 8, 8),
                Width = 120,
            };
            var stack = new StackPanel();

            var title = new TextBlock
            {
                Text = channel,
                FontWeight = FontWeights.SemiBold,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
                TextAlignment = System.Windows.TextAlignment.Center,
            };

            var volumeText = new TextBlock
            {
                Text = "0%",
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
                Margin = new Thickness(0, 4, 0, 2),
            };

            var slider = new Slider
            {
                Minimum = 0,
                Maximum = 100,
                Orientation = System.Windows.Controls.Orientation.Vertical,
                IsDirectionReversed = true,
                Height = 140,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
            };
            slider.ValueChanged += (_, _) => { if (!_suspendUpdates) volumeText.Text = $"{(int)slider.Value}%"; };
            slider.PreviewMouseLeftButtonUp += async (_, _) =>
            {
                if (_suspendUpdates) return;
                await _api.SetChannelVolumeAsync(channel, (int)slider.Value, _cts.Token);
            };
            slider.TouchUp += async (_, _) =>
            {
                if (_suspendUpdates) return;
                await _api.SetChannelVolumeAsync(channel, (int)slider.Value, _cts.Token);
            };

            var mute = new System.Windows.Controls.CheckBox
            {
                Content = "Mute",
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
                Margin = new Thickness(0, 6, 0, 4),
            };
            mute.Click += async (_, _) =>
            {
                if (_suspendUpdates) return;
                await _api.SetChannelMuteAsync(channel, mute.IsChecked == true, _cts.Token);
            };

            var preset = new System.Windows.Controls.ComboBox
            {
                MinWidth = 96,
                MaxWidth = 96,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
            };
            preset.SelectionChanged += async (_, _) =>
            {
                if (_suspendUpdates) return;
                if (preset.SelectedItem is ComboBoxItem item && item.Tag is string id)
                {
                    if (id == "__none__") return;
                    await _api.SetChannelPresetAsync(channel, id, _cts.Token);
                }
            };

            var apps = new TextBlock
            {
                Text = "N/A",
                Margin = new Thickness(0, 6, 0, 0),
                Foreground = (System.Windows.Media.Brush)new System.Windows.Media.BrushConverter().ConvertFromString("#FF9BA8B7"),
                TextWrapping = TextWrapping.Wrap,
                MaxHeight = 56,
            };

            stack.Children.Add(title);
            stack.Children.Add(slider);
            stack.Children.Add(volumeText);
            stack.Children.Add(mute);
            stack.Children.Add(preset);
            stack.Children.Add(apps);
            rowBorder.Child = stack;
            ChannelsPanel.Children.Add(rowBorder);

            _rows[channel] = new ChannelRow(slider, volumeText, mute, preset, apps);
        }
    }

    private void MoveToBottomRight()
    {
        var area = SystemParameters.WorkArea;
        Left = area.Right - Width - 20;
        Top = area.Bottom - Height - 28;
    }

    private void ApplyNativeWindowEffects()
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        if (hwnd == IntPtr.Zero) return;
        const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;
        const int DWMWCP_ROUND = 2;
        var pref = DWMWCP_ROUND;
        DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref pref, Marshal.SizeOf<int>());
        const int DWMWA_SYSTEMBACKDROP_TYPE = 38;
        const int DWMSBT_MAINWINDOW = 2;
        var backdrop = DWMSBT_MAINWINDOW;
        DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ref backdrop, Marshal.SizeOf<int>());
    }

    private static string YN(bool? value) => value is null ? "N/A" : value.Value ? "Yes" : "No";
    private static string PercentOrNA(int? value) => value.HasValue ? $"{value.Value}%" : "N/A";

    private static string BuildStateRenderKey(DashboardState state)
    {
        var sb = new StringBuilder(512);
        sb.Append(state.status).Append('|').Append(state.last_error).Append('|');
        sb.Append(state.connected).Append('|').Append(state.wireless).Append('|').Append(state.bluetooth).Append('|');
        sb.Append(state.anc_mode).Append('|').Append(state.mic_mute).Append('|').Append(state.sidetone_level).Append('|');
        sb.Append(state.chat_mix_balance).Append('|').Append(state.oled_brightness).Append('|').Append(state.headset_volume_percent).Append('|');
        sb.Append(state.headset_battery_percent).Append('|').Append(state.base_battery_percent).Append('|');

        AppendDict(sb, state.channel_volume);
        AppendDict(sb, state.channel_mute);
        AppendDict(sb, state.channel_preset);
        if (state.channel_apps is not null)
        {
            foreach (var key in state.channel_apps.Keys.OrderBy(k => k))
            {
                sb.Append(key).Append('=').Append(string.Join(",", state.channel_apps[key])).Append(';');
            }
        }
        return sb.ToString();
    }

    private static string BuildPresetsRenderKey(Dictionary<string, List<PresetItem>> presets)
    {
        var sb = new StringBuilder(512);
        foreach (var key in presets.Keys.OrderBy(k => k))
        {
            sb.Append(key).Append(':');
            foreach (var p in presets[key])
            {
                sb.Append(p.id).Append('=').Append(p.name).Append(',');
            }
            sb.Append(';');
        }
        return sb.ToString();
    }

    private static void AppendDict<T>(StringBuilder sb, Dictionary<string, T>? dict)
    {
        if (dict is null) return;
        foreach (var key in dict.Keys.OrderBy(k => k))
        {
            sb.Append(key).Append('=').Append(dict[key]).Append(';');
        }
    }

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int dwAttribute, ref int pvAttribute, int cbAttribute);

    private sealed record ChannelRow(
        Slider VolumeSlider,
        TextBlock VolumeText,
        System.Windows.Controls.CheckBox MuteCheck,
        System.Windows.Controls.ComboBox PresetCombo,
        TextBlock AppsText
    );
}
