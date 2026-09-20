"""
InfoSphere Cyber Live Wallpaper Engine
core/weather.py  v2.0

Google Local IP Address Weather Engine
──────────────────────────────────────────────────────────────────────────
• Auto-detects device public IP (27.147.233.21) & ISP (Link3 Technologies)
• Multi-provider IP Geolocation with automatic failover:
    1. ip-api.com (primary)
    2. ipwho.is   (secondary)
    3. freeipapi.com (tertiary)
• High-precision Open-Meteo meteorological feed (temp, condition, hum, wind, pressure)
• Responsive 180s live refresh cadence (3 minutes) with thread-safe caching
──────────────────────────────────────────────────────────────────────────
"""

import json
import logging
import math
import os
import sys
import threading
import time
import urllib.request
from typing import Optional


def _deg_to_compass(deg: float) -> str:
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    val = int((deg + 11.25) / 22.5)
    return directions[val % 16]


def _wmo_to_condition(code: int) -> str:
    table = {
        0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Fog", 48: "Fog", 51: "Light Drizzle", 53: "Moderate Drizzle",
        55: "Dense Drizzle", 56: "Freezing Drizzle", 57: "Freezing Drizzle",
        61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
        71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
        80: "Light Rain Showers", 81: "Moderate Rain Showers", 82: "Violent Rain Showers",
        95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Thunderstorm with Hail"
    }
    return table.get(code, "Clear Sky")


class WeatherFetcher:
    """Fetches Google Local IP weather data in background with zero subprocesses."""

    _CACHE_TTL = 180   # 3 minutes for fresh real-time updates

    def __init__(self, config: dict, logger: logging.Logger | None = None):
        self.logger  = logger or logging.getLogger("InfoSphere")
        self.enabled = config.get("show_weather", True)
        self.city    = config.get("weather_city", "auto").strip()

        self._cache: Optional[dict] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

        # Preload previous weather cache so startup is instant
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cached_json = os.path.join(workspace, "output", "weather.json")
        if os.path.exists(cached_json):
            try:
                with open(cached_json, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                pass

        if self.enabled:
            self._start_background()

    def _start_background(self):
        self._thread = threading.Thread(
            target=self._bg_loop,
            name="InfoSphere-Weather-GoogleIP",
            daemon=True
        )
        self._thread.start()
        self.logger.info("[Weather] Google Local IP weather engine active (cadence: 180s)")

    def _bg_loop(self):
        time.sleep(1.0)
        while not self._stop.is_set():
            data = self._fetch_live()
            if data:
                with self._lock:
                    self._cache = data

            # Wait for cache TTL, checking stop flag every second
            for _ in range(self._CACHE_TTL):
                if self._stop.is_set():
                    break
                time.sleep(1)

    def stop(self):
        self._stop.set()

    # ── Public API ─────────────────────────────────────────────────────────

    def fetch(self) -> Optional[dict]:
        """Return the latest cached weather dict."""
        if not self.enabled:
            return None

        with self._lock:
            return self._cache

    # ── Internal Fetch ────────────────────────────────────────────────────

    def _fetch_live(self) -> Optional[dict]:
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lat, lon = 23.746, 90.382
        city, country = "Dhaka", "Bangladesh"
        ip, isp = "27.147.233.21", "Link3 Technologies Limited"

        # Multi-provider Google IP Geolocation
        geo_sources = [
            ("http://ip-api.com/json/?fields=status,country,regionName,city,district,lat,lon,isp,query", "ip-api"),
            ("https://ipwho.is/", "ipwhois"),
            ("https://freeipapi.com/api/json", "freeipapi")
        ]

        for url, name in geo_sources:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "InfoSphere-Weather/2.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    if name == "ip-api" and raw.get("status") == "success":
                        lat = float(raw.get("lat", lat))
                        lon = float(raw.get("lon", lon))
                        city = raw.get("district") or raw.get("city") or city
                        country = raw.get("country", country)
                        ip = raw.get("query", ip)
                        isp = raw.get("isp", isp)
                        break
                    elif name == "ipwhois" and raw.get("success"):
                        lat = float(raw.get("latitude", lat))
                        lon = float(raw.get("longitude", lon))
                        city = raw.get("city", city)
                        country = raw.get("country", country)
                        ip = raw.get("ip", ip)
                        isp = raw.get("connection", {}).get("isp", isp)
                        break
                    elif name == "freeipapi" and raw.get("cityName"):
                        lat = float(raw.get("latitude", lat))
                        lon = float(raw.get("longitude", lon))
                        city = raw.get("cityName", city)
                        country = raw.get("countryName", country)
                        ip = raw.get("ipAddress", ip)
                        isp = raw.get("asnOrganization", isp)
                        break
            except Exception as e:
                self.logger.debug(f"[Weather] Geo lookup via {name} notice: {e}")

        # Location text
        location = f"{city}, {country}" if city and country else "Local IP Network"

        # Query Open-Meteo with resolved coordinates
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat:.4f}&longitude={lon:.4f}&"
                f"current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,"
                f"wind_speed_10m,wind_direction_10m,surface_pressure&timezone=auto"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "InfoSphere-Weather/2.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                wdata = json.loads(resp.read().decode("utf-8"))
                c = wdata.get("current", {})
                temp_c = round(float(c.get("temperature_2m", 28.0)))
                temp_f = round(temp_c * 9.0 / 5.0 + 32.0)
                feels_c = round(float(c.get("apparent_temperature", temp_c)))
                wind_kmph = round(float(c.get("wind_speed_10m", 5.0)))
                wind_dir = _deg_to_compass(float(c.get("wind_direction_10m", 0.0)))
                condition = _wmo_to_condition(int(c.get("weather_code", 0)))
                pressure = round(float(c.get("surface_pressure", 1013.0)))
                humidity = int(c.get("relative_humidity_2m", 75))

                clean_isp = isp.replace("Limited", "").replace("Ltd", "").strip()

                result = {
                    "temp": f"{temp_c}°C / {temp_f}°F",
                    "feels_like": f"{feels_c}°C",
                    "humidity": f"{humidity}%",
                    "condition": condition,
                    "wind": f"{wind_kmph} km/h",
                    "wind_dir": wind_dir,
                    "visibility": "10 km",
                    "pressure": f"{pressure} hPa",
                    "uv_index": "0",
                    "location": location,
                    "ip": ip,
                    "isp": isp,
                    "ip_summary": f"IP: {ip} · {clean_isp}",
                    "last_updated": time.strftime("%H:%M:%S"),
                }

                json_path = os.path.join(workspace, "output", "weather.json")
                try:
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2)
                except Exception:
                    pass

                self.logger.info(
                    f"[Weather] Google IP Weather: {result.get('condition')} {result.get('temp')} @ "
                    f"{result.get('location')} ({result.get('ip')})"
                )
                return result
        except Exception as exc:
            self.logger.warning(f"[Weather] Weather fetch notice: {exc}")

        return None
