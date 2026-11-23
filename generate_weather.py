#!/usr/bin/env python3
"""
Kindle Paperwhite weather dashboard with drawn weather icons.
Data: Open-Meteo (MeteoSwiss ICON CH2) — free, no API key.
"""
import sys
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
from PIL import Image, ImageDraw, ImageFont

# ── Configuration ─────────────────────────────────────────────────────
LAT      = 46.5225
LON      = 6.5700
LOCATION = "Ecublens, 1024"
TZ       = "Europe/Zurich"
W, H     = 1072, 1448   # PW3 / PW4

FONT      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ── WMO label map ─────────────────────────────────────────────────────
WMO_LABEL = {
    0: "Clear",     1: "Clear",    2: "P.Cloudy",  3: "Overcast",
    45: "Fog",      48: "Icy Fog",
    51: "Drizzle",  53: "Drizzle", 55: "Drizzle",
    61: "L.Rain",   63: "Rain",    65: "H.Rain",
    71: "L.Snow",   73: "Snow",    75: "H.Snow",
    80: "Showers",  81: "Showers", 82: "H.Showers",
    85: "S.Shower", 86: "S.Shower",
    95: "Thunder",  96: "Thunder", 99: "Thunder",
}

def wmo(code):
    return WMO_LABEL.get(code, f"Code {code}")

# ── Weather icons (drawn with Pillow) ─────────────────────────────────

def _sun(draw, cx, cy, r, lw, fill=0):
    cr = int(r * 0.40)
    draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], fill=fill)
    for i in range(8):
        a = i * math.pi / 4
        x1 = int(cx + (cr + lw*2) * math.cos(a))
        y1 = int(cy + (cr + lw*2) * math.sin(a))
        x2 = int(cx + r * math.cos(a))
        y2 = int(cy + r * math.sin(a))
        draw.line([x1, y1, x2, y2], fill=fill, width=lw)

def _cloud(draw, cx, cy, r, fill=0):
    """Filled cloud silhouette."""
    # Three bumps + flat bottom rectangle
    bumps = [
        (cx - int(r*0.32), cy - int(r*0.05), int(r*0.36)),
        (cx + int(r*0.08), cy - int(r*0.28), int(r*0.42)),
        (cx + int(r*0.42), cy - int(r*0.05), int(r*0.30)),
    ]
    for bx, by, br in bumps:
        draw.ellipse([bx-br, by-br, bx+br, by+br], fill=fill)
    draw.rectangle(
        [cx - int(r*0.68), cy - int(r*0.05),
         cx + int(r*0.72), cy + int(r*0.52)],
        fill=fill
    )

def _rain_lines(draw, cx, cy, r, n, lw, fill=0):
    top_y = cy + int(r * 0.52)
    drop  = int(r * 0.30)
    gap   = int(r * 1.1 / max(n - 1, 1))
    x0    = cx - int(r * 0.45)
    for i in range(n):
        x = x0 + i * gap
        dy = int(r * 0.08) if i % 2 else 0
        draw.line([x, top_y + dy, x - int(drop*0.35), top_y + dy + drop],
                  fill=fill, width=lw)

def _snow_dots(draw, cx, cy, r, lw, fill=0):
    top_y = cy + int(r * 0.56)
    fr    = max(lw + 1, int(r * 0.07))
    for fx, fy in [
        (cx - int(r*0.35), top_y),
        (cx,               top_y + int(r*0.08)),
        (cx + int(r*0.35), top_y),
        (cx - int(r*0.17), top_y + int(r*0.26)),
        (cx + int(r*0.17), top_y + int(r*0.26)),
    ]:
        for a in [0, math.pi/3, 2*math.pi/3]:
            x1, y1 = int(fx + fr*math.cos(a)), int(fy + fr*math.sin(a))
            x2, y2 = int(fx - fr*math.cos(a)), int(fy - fr*math.sin(a))
            draw.line([x1, y1, x2, y2], fill=fill, width=lw)

def _bolt(draw, cx, cy, r, lw, fill=0):
    sy = cy + int(r * 0.50)
    pts = [
        (cx + int(r*0.12), sy),
        (cx - int(r*0.06), sy + int(r*0.22)),
        (cx + int(r*0.06), sy + int(r*0.22)),
        (cx - int(r*0.16), sy + int(r*0.52)),
    ]
    draw.line(pts, fill=fill, width=lw*2)

def _fog_lines(draw, cx, cy, r, lw, fill=0):
    for i in range(4):
        y  = int(cy - r*0.25) + i * int(r*0.22)
        x0 = cx - int(r*(0.65 if i%2==0 else 0.55))
        x1 = cx + int(r*(0.55 if i%2==0 else 0.65))
        draw.line([x0, y, x1, y], fill=fill, width=lw)

def draw_icon(draw, cx, cy, size, code):
    """Draw a weather icon centred at (cx, cy)."""
    r  = size // 2
    lw = max(3, size // 18)

    if code in (0, 1):
        _sun(draw, cx, cy, r, lw)

    elif code == 2:                              # partly cloudy
        # Small sun top-left, cloud bottom-right
        _sun(draw, cx - int(r*0.22), cy - int(r*0.22), int(r*0.60), max(2, lw-1))
        # Erase sun behind cloud with white fill, then draw cloud in black
        _cloud(draw, cx + int(r*0.08), cy + int(r*0.10), int(r*0.78), fill=255)
        _cloud(draw, cx + int(r*0.08), cy + int(r*0.10), int(r*0.78), fill=0)

    elif code == 3:
        _cloud(draw, cx, cy, r)

    elif code in (45, 48):
        _fog_lines(draw, cx, cy, r, lw)

    elif code in (51, 53, 55, 61, 63):
        _cloud(draw, cx, cy - int(r*0.15), int(r*0.82))
        _rain_lines(draw, cx, cy, r, n=3, lw=lw)

    elif code in (65, 80, 81, 82):
        _cloud(draw, cx, cy - int(r*0.15), int(r*0.82))
        _rain_lines(draw, cx, cy, r, n=5, lw=lw)

    elif code in (71, 73, 75, 85, 86):
        _cloud(draw, cx, cy - int(r*0.15), int(r*0.82))
        _snow_dots(draw, cx, cy, r, lw)

    elif code in (95, 96, 99):
        _cloud(draw, cx, cy - int(r*0.20), int(r*0.78))
        _bolt(draw, cx, cy, r, lw)

    else:
        _cloud(draw, cx, cy, r)

# ── Open-Meteo fetch ──────────────────────────────────────────────────

def fetch():
    params = {
        "latitude": LAT, "longitude": LON,
        "current": ["temperature_2m", "apparent_temperature",
                    "weather_code", "wind_speed_10m",
                    "relative_humidity_2m"],
        "daily": ["weather_code", "temperature_2m_max",
                  "temperature_2m_min", "precipitation_probability_max",
                  "sunrise", "sunset"],
        "hourly": ["precipitation_probability", "precipitation"],
        "models": "meteoswiss_icon_ch2",
        "timezone": TZ,
        "forecast_days": 5,
    }
    import time
    for attempt in range(5):
        try:
            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=(10, 60),  # 10s connect, 60s read
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt == 4:
                raise
            wait = 10 * (attempt + 1)  # 10s, 20s, 30s, 40s
            print(f"Attempt {attempt + 1} failed: {e} — retrying in {wait}s...")
            time.sleep(wait)

# ── Render ────────────────────────────────────────────────────────────

def fnt(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

def render(data, out):
    cur    = data["current"]
    daily  = data["daily"]
    hourly = data["hourly"]

    img  = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(img)
    M = 44

    f_xs = fnt(FONT,      28)
    f_s  = fnt(FONT,      38)
    f_m  = fnt(FONT,      52)
    f_l  = fnt(FONT_BOLD, 100)
    f_xl = fnt(FONT_BOLD, 158)

    y = M

    # ── Shared chart setup ────────────────────────────────────────────
    Y_LBL   = 58
    chart_h = 108
    bw      = (W - 2*M - Y_LBL) // 24
    cx0     = M + Y_LBL
    today   = daily["time"][0]
    try:
        idx0 = hourly["time"].index(f"{today}T00:00")
    except ValueError:
        idx0 = 0
    probs  = hourly["precipitation_probability"]
    precip = hourly.get("precipitation", [])

    # ── Header ────────────────────────────────────────────────────────
    now_local = datetime.now(ZoneInfo(TZ)).strftime("%a %d %b  %H:%M")
    draw.text((M, y),     LOCATION,  font=f_m,  fill=0)
    draw.text((W-M, y+8), now_local, font=f_xs, fill=80, anchor="ra")
    y += 68
    draw.line([(M, y), (W-M, y)], fill=0, width=3)
    y += 28

    # ── Current conditions ────────────────────────────────────────────
    temp = cur["temperature_2m"]
    feel = cur["apparent_temperature"]
    hum  = cur["relative_humidity_2m"]
    wind = cur["wind_speed_10m"]
    code = cur["weather_code"]

    draw.text((M, y), f"{temp:.0f}", font=f_xl, fill=0)
    bbox = draw.textbbox((M, y), f"{temp:.0f}", font=f_xl)
    draw.text((bbox[2]+6, y+16), "\u00b0C", font=f_l, fill=0)

    icon_size = 220
    draw_icon(draw, W//2 + 20, y + icon_size//2 + 10, icon_size, code)

    rx = W - M
    draw.text((rx, y),       wmo(code),                   font=f_m, fill=0,  anchor="ra")
    draw.text((rx, y + 68),  f"Feels: {feel:.0f}\u00b0C", font=f_s, fill=70, anchor="ra")
    draw.text((rx, y + 118), f"Humidity: {hum:.0f}%",     font=f_s, fill=70, anchor="ra")
    draw.text((rx, y + 168), f"Wind: {wind:.0f} km/h",    font=f_s, fill=70, anchor="ra")

    y += icon_size + 24

    sr = daily["sunrise"][0].split("T")[1][:5]
    ss = daily["sunset"][0].split("T")[1][:5]
    draw.text((M, y), f"\u2191 {sr}   \u2193 {ss}", font=f_s, fill=70)
    y += 58

    draw.line([(M, y), (W-M, y)], fill=0, width=3)
    y += 32

    # ── Chart 1: rainfall mm ──────────────────────────────────────────
    draw.text((M, y), "Rainfall", font=f_m, fill=0)
    y += 80

    rain_24 = [precip[idx0+h] if (idx0+h) < len(precip) else 0.0 for h in range(24)]
    raw_max = max(rain_24) if rain_24 else 0.0
    if   raw_max <= 0:   scale_mm = 1.0
    elif raw_max <= 1:   scale_mm = 1.0
    elif raw_max <= 2:   scale_mm = 2.0
    elif raw_max <= 5:   scale_mm = 5.0
    elif raw_max <= 10:  scale_mm = 10.0
    else:                scale_mm = math.ceil(raw_max / 5) * 5.0

    for frac, label in [(0, "0"), (0.5, f"{scale_mm/2:.1f}"), (1.0, f"{scale_mm:.0f}mm")]:
        yy = y + chart_h - int(chart_h * frac)
        draw.text((cx0 - 6, yy), label, font=f_xs, fill=80, anchor="rm")
        if frac in (0.5, 1.0):
            draw.line([(cx0, yy), (W-M, yy)], fill=210, width=1)

    for h in range(24):
        mm = rain_24[h]
        bh = min(chart_h, int(chart_h * mm / scale_mm)) if scale_mm > 0 else 0
        bx = cx0 + h * bw
        if bh > 0:
            draw.rectangle([bx+1, y+chart_h-bh, bx+bw-1, y+chart_h], fill=0)
        if h % 6 == 0:
            draw.text((bx + bw//2, y+chart_h+5), f"{h:02d}h",
                      font=f_xs, fill=0, anchor="mt")

    y += chart_h + 44
    draw.line([(M, y), (W-M, y)], fill=180, width=1)
    y += 24

    # ── Chart 2: precipitation probability ───────────────────────────
    draw.text((M, y), "Precipitation probability", font=f_m, fill=0)
    y += 80

    for pct, label in [(0, "0%"), (50, "50%"), (100, "100%")]:
        yy = y + chart_h - int(chart_h * pct / 100)
        draw.text((cx0 - 6, yy), label, font=f_xs, fill=80, anchor="rm")
        if pct in (50, 100):
            draw.line([(cx0, yy), (W-M, yy)], fill=210, width=1)

    for h in range(24):
        p  = probs[idx0+h] if (idx0+h) < len(probs) else 0
        bh = int(chart_h * p / 100)
        bx = cx0 + h * bw
        draw.rectangle([bx+1, y+chart_h-bh, bx+bw-1, y+chart_h], fill=0)
        if h % 6 == 0:
            draw.text((bx + bw//2, y+chart_h+5), f"{h:02d}h",
                      font=f_xs, fill=0, anchor="mt")

    y += chart_h + 44
    draw.line([(M, y), (W-M, y)], fill=0, width=3)
    y += 32

    # ── 5-day forecast ────────────────────────────────────────────────
    draw.text((M, y), "5-Day Forecast", font=f_m, fill=0)
    y += 64

    n   = min(5, len(daily["time"]))
    col = (W - 2*M) // n

    for i in range(n):
        fcx  = M + i*col + col//2
        date = datetime.fromisoformat(daily["time"][i])
        lbl  = "Today" if i == 0 else date.strftime("%a %d")
        hi   = daily["temperature_2m_max"][i]
        lo   = daily["temperature_2m_min"][i]
        prob = daily["precipitation_probability_max"][i]
        dc   = daily["weather_code"][i] or 0
        ico_sz = int(col * 0.60)
        hi_str   = f"{hi:.0f}\u00b0"  if hi   is not None else "null"
        lo_str   = f"{lo:.0f}\u00b0"  if lo   is not None else "null"
        prob_str = f"P:{prob:.0f}%"    if prob is not None else "P:null"

        draw.text((fcx, y),                        lbl,      font=f_s,  fill=0,   anchor="mt")
        draw_icon(draw, fcx, y + 48 + ico_sz//2, ico_sz, dc)
        draw.text((fcx, y + 48 + ico_sz + 4),   wmo(dc),    font=f_xs, fill=80,  anchor="mt")
        draw.text((fcx, y + 48 + ico_sz + 36),  hi_str,     font=f_m,  fill=0,   anchor="mt")
        draw.text((fcx, y + 48 + ico_sz + 100), lo_str,     font=f_s,  fill=100, anchor="mt")
        draw.text((fcx, y + 48 + ico_sz + 148), prob_str,   font=f_xs, fill=80,  anchor="mt")

        if i < n-1:
            sx = M + (i+1)*col
            draw.line([(sx, y), (sx, y + 48 + ico_sz + 184)], fill=180, width=1)

    y += 48 + ico_sz + 198

    img.save(out, "PNG")
    print(f"Saved {out}  ({W}x{H})")

if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "weather.png"
    render(fetch(), out_path)
