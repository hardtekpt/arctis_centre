using System.Net.Http;
using System.Net.Http.Json;
using NativeDashboard.Models;

namespace NativeDashboard.Services;

public sealed class BackendApiClient
{
    private readonly HttpClient _http;

    public BackendApiClient(string baseUrl)
    {
        _http = new HttpClient
        {
            BaseAddress = new Uri(baseUrl),
            Timeout = TimeSpan.FromSeconds(8),
        };
    }

    public async Task<DashboardState?> GetStateAsync(CancellationToken ct)
    {
        return await _http.GetFromJsonAsync<DashboardState>("/state", ct);
    }

    public async Task<Dictionary<string, List<PresetItem>>> GetPresetsAsync(CancellationToken ct)
    {
        var result = await _http.GetFromJsonAsync<Dictionary<string, List<PresetItem>>>("/presets", ct);
        return result ?? new Dictionary<string, List<PresetItem>>();
    }

    public async Task SetChannelVolumeAsync(string channel, int value, CancellationToken ct)
    {
        var payload = new { channel, value };
        using var resp = await _http.PostAsJsonAsync("/actions/channel-volume", payload, ct);
        resp.EnsureSuccessStatusCode();
    }

    public async Task SetChannelMuteAsync(string channel, bool muted, CancellationToken ct)
    {
        var payload = new { channel, muted };
        using var resp = await _http.PostAsJsonAsync("/actions/channel-mute", payload, ct);
        resp.EnsureSuccessStatusCode();
    }

    public async Task SetChannelPresetAsync(string channel, string presetId, CancellationToken ct)
    {
        var payload = new { channel, preset_id = presetId };
        using var resp = await _http.PostAsJsonAsync("/actions/channel-preset", payload, ct);
        resp.EnsureSuccessStatusCode();
    }
}

public sealed class PresetItem
{
    public string id { get; set; } = "";
    public string name { get; set; } = "";
}
