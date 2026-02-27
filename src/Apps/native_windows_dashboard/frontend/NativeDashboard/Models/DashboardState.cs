namespace NativeDashboard.Models;

public sealed class DashboardState
{
    public int? headset_battery_percent { get; set; }
    public int? base_battery_percent { get; set; }
    public int? headset_volume_percent { get; set; }
    public string? anc_mode { get; set; }
    public bool? mic_mute { get; set; }
    public int? sidetone_level { get; set; }
    public bool? connected { get; set; }
    public bool? wireless { get; set; }
    public bool? bluetooth { get; set; }
    public int? chat_mix_balance { get; set; }
    public int? oled_brightness { get; set; }
    public Dictionary<string, int>? channel_volume { get; set; }
    public Dictionary<string, bool>? channel_mute { get; set; }
    public Dictionary<string, string?>? channel_preset { get; set; }
    public Dictionary<string, string?>? channel_preset_name { get; set; }
    public Dictionary<string, List<string>>? channel_apps { get; set; }
    public string? updated_at { get; set; }
    public string? status { get; set; }
    public string? last_error { get; set; }
}
