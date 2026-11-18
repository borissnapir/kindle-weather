#!/usr/bin/env python3
"""
Kindle Paperwhite weather dashboard generator.
Data: Open-Meteo (MeteoSwiss ICON CH2) — free, no API key.
Output: grayscale PNG at Kindle screen resolution.
"""
import sys
from datetime import datetime, timezone
import requests
from PIL import Image, ImageDraw, ImageFont

# ── Configuration ────────────────────────────────────────────────────
LAT      = 46.5225
LON      = 6.5700
LOCATION = "Ecublens, 1024"
TZ       = "Europe/Zurich"

# Screen dimensions — adjust for your Kindle model:
#   PW2 (2013-2014):       758  x 1024
#   PW3 / PW4 (2015-2021): 1072 x 1448  ← default
#   PW5 / PW6 (2021-2024): 1236 x 1648
W, H = 1072, 1448

FONT      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ── WMO weather code → short label ───────────────────────────────────
WMO_LABEL: dict[int, str] = {
    0: "Clear",    1: "Clear+",   2: "P.Cloudy",  3: "Overcast",
    45: "Fog",    48: "Icy Fog",
    51: "Drizzle", 53: "Drizzle",  55: "Drizzle",
    61: "L.Rain",  63: "Rain",     65: "H.Rain",
    71: "L.Snow",  73: "Snow",     75: "H.Snow",
    80: "Showers", 81: "Showers",  82: "H.Shower",
    85: "S.Shower",86: "S.Shower",
    95: "Thunder", 96: "Thunder",  99: "Thunder",
}

def wmo(code: int) -> str:
    return WMO_LABEL.get(code, f"Code {code}")


def fetch() -> dict:
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": LAT, "longitude": LON,
            "current": [
                "temperature_2m", "apparent_temperature", "weather_code",
                "wind_speed_10m", "relative_humidity_2m",
            ],
            "daily": [
                "weather_code", "temperature_2m_max", "temperature_2m_min",
                "precipitation_probability_max", "sunrise", "sunset",
            ],
            "hourly": ["precipitation_probability"],
            "models": "meteoswiss_icon_ch2",
            "timezone": TZ,
            "forecast_days": 5,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fnt(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def render(data: dict, out: str) -> None:
    cur    = data["current"]
    daily  = data["daily"]
    hourly = data["hourly"]

    img  = Image.new("L", (W, H), 255)   # white (255) background
    draw = ImageDraw.Draw(img)

    M = 44  # horizontal margin

    f_xs = fnt(FONT,      28)
    f_s  = fnt(FONT,      38)
    f_m  = fnt(FONT,      52)
    f_l  = fnt(FONT_BOLD, 100)
    f_xl = fnt(FONT_BOLD, 160)

    y = M

    # ── Header ───────────────────────────────────────────────────────
    now_utc = datetime.now(timezone.utc).strftime("%a %d %b  %H:%M UTC")
    draw.text((M, y),       LOCATION, font=f_m, fill=0)
    draw.text((W - M, y + 8), now_utc, font=f_xs, fill=80, anchor="ra")
    y += 68
    draw.line([(M, y), (W - M, y)], fill=0, width=3)
    y += 28

    # ── Current conditions ───────────────────────────────────────────
    temp = cur["temperature_2m"]
    feel = cur["apparent_temperature"]
    hum  = cur["relative_humidity_2m"]
    wind = cur["wind_speed_10m"]

    draw.text((M, y), f"{temp:.0f}", font=f_xl, fill=0)
    bbox = draw.textbbox((M, y), f"{temp:.0f}", font=f_xl)
    draw.text((bbox[2] + 8, y + 20), "\u00b0C", font=f_l, fill=0)   # °C

    rx = M + 580
    draw.text((rx, y + 10),  wmo(cur["weather_code"]),  font=f_m, fill=0)
    draw.text((rx, y + 76),  f"Feels: {feel:.0f}\u00b0C", font=f_s, fill=70)
    draw.text((rx, y + 128), f"Humidity: {hum:.0f}%",    font=f_s, fill=70)
    draw.text((rx, y + 180), f"Wind: {wind:.0f} km/h",   font=f_s, fill=70)
    y += 250

    # Sunrise / sunset  (↑ U+2191, ↓ U+2193)
    sr = daily["sunrise"][0].split("T")[1][:5]
    ss = daily["sunset"][0].split("T")[1][:5]
    draw.text((M, y), f"\u2191 {sr}   \u2193 {ss}", font=f_s, fill=70)
    y += 60

    draw.line([(M, y), (W - M, y)], fill=0, width=3)
    y += 32

    # ── 5-day forecast ───────────────────────────────────────────────
    draw.text((M, y), "5-Day Forecast", font=f_m, fill=0)
    y += 64

    n   = min(5, len(daily["time"]))
    col = (W - 2 * M) // n

    for i in range(n):
        cx   = M + i * col + col // 2
        date = datetime.fromisoformat(daily["time"][i])
        lbl  = "Today" if i == 0 else date.strftime("%a %d")
        hi   = daily["temperature_2m_max"][i]
        lo   = daily["temperature_2m_min"][i]
        prob = daily["precipitation_probability_max"][i] or 0
        code = daily["weather_code"][i]

        draw.text((cx, y),       lbl,            font=f_s,  fill=0,   anchor="mt")
        draw.text((cx, y + 48),  wmo(code),      font=f_xs, fill=80,  anchor="mt")
        draw.text((cx, y + 86),  f"{hi:.0f}\u00b0", font=f_m, fill=0, anchor="mt")
        draw.text((cx, y + 148), f"{lo:.0f}\u00b0", font=f_s, fill=100, anchor="mt")
        draw.text((cx, y + 194), f"P: {prob:.0f}%", font=f_xs, fill=80, anchor="mt")

        if i < n - 1:
            sep_x = M + (i + 1) * col
            draw.line([(sep_x, y), (sep_x, y + 234)], fill=180, width=1)

    y += 248
    draw.line([(M, y), (W - M, y)], fill=0, width=3)
    y += 32

    # ── Hourly precipitation probability — next 24 h ─────────────────
    draw.text((M, y), "Precipitation probability — next 24h", font=f_s, fill=0)
    y += 56

    chart_h = 130
    bar_w   = (W - 2 * M) // 24

    today = daily["time"][0]
    try:
        idx0 = hourly["time"].index(f"{today}T00:00")
    except ValueError:
        idx0 = 0

    probs = hourly["precipitation_probability"]
    for h in range(24):
        p  = probs[idx0 + h] if (idx0 + h) < len(probs) else 0
        bh = int(chart_h * p / 100)
        bx = M + h * bar_w
        draw.rectangle(
            [bx + 2, y + chart_h - bh, bx + bar_w - 2, y + chart_h],
            fill=0,
        )
        if h % 6 == 0:
            draw.text(
                (bx + bar_w // 2, y + chart_h + 6),
                f"{h:02d}h",
                font=f_xs, fill=0, anchor="mt",
            )

    y += chart_h + 46
    draw.line([(M, y), (W - M, y)], fill=0, width=3)
    y += 18

    # ── Attribution ──────────────────────────────────────────────────
    draw.text(
        (W // 2, y),
        "Data: Open-Meteo / MeteoSwiss ICON CH2  (CC BY 4.0)",
        font=f_xs, fill=120, anchor="mt",
    )

    img.save(out, "PNG")
    print(f"Saved {out}  ({W}x{H})")


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "weather.png"
    render(fetch(), out_path)
