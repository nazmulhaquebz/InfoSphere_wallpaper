import datetime
import json
import unittest
from unittest.mock import patch

try:
    from core.cyber_generator import CyberWallpaperGenerator
except ImportError:
    CyberWallpaperGenerator = None
from core.display_info import resolve_display_config
from core.telemetry_snapshot import build_snapshot, validate_snapshot


def sample_system():
    return {
        "hostname": "AUDIT-HOST",
        "username": "LOCAL",
        "os_name": "Windows Test",
        "local_ip": "192.168.1.20",
        "cpu_percent": 32.5,
        "cpu_cores": [20, 30, 40, 50, 15, 25, 35, 45],
        "cpu_temp": 54.2,
        "cpu_temp_source": "GPU_PROXY_ESTIMATE",
        "ram_percent": 48.0,
        "ram_used_gb": 8.0,
        "ram_total_gb": 16.0,
        "disk_percent": 60.0,
        "disk_used_gb": 300.0,
        "disk_total_gb": 500.0,
        "uptime": "02h 10m",
        "uptime_secs": 7800,
        "process_count": 180,
        "bg_process_count": 45,
        "wifi_status": "CONNECTED",
        "wifi_ssid": "Audit Network",
        "wifi_signal": "78%",
        "wifi_speed": "433 Mbps",
        "wifi_bssid": "00:11:22:33:44:55",
        "wifi_band": "5 GHz",
        "net_tx_speed": "12.5 KB/s",
        "net_rx_speed": "80.2 KB/s",
        "net_tx_kbps": 12.5,
        "net_rx_kbps": 80.2,
        "net_sent_mb": 1024.0,
        "net_recv_mb": 2048.0,
        "firewall_status": "ACTIVE",
        "time_now": datetime.datetime(2026, 8, 1, 12, 0, 0),
    }


def sample_router(count=24):
    clients = []
    for index in range(count):
        clients.append({
            "name": f"Device-{index:02d}",
            "ip": f"192.168.1.{index + 2}",
            "mac": f"00:11:22:33:44:{index:02X}",
            "band": "5 GHz" if index % 2 else "2.4 GHz",
            "rssi": 70,
            "tx_mb": float(index),
            "rx_mb": float(index * 2),
        })
    return {
        "status": "ONLINE [TEST]",
        "total_online": count,
        "band_5_count": count // 2,
        "band_24_count": count - count // 2,
        "wired_count": 0,
        "tx_total_mb": 1200.0,
        "rx_total_mb": 2400.0,
        "clients": clients,
        "timestamp": 1,
    }


def base_config(width=1920, height=1080):
    return {
        "resolution_width": width,
        "resolution_height": height,
        "refresh_interval_seconds": 10,
        "output_path": "output/test_regression.png",
        "simulate_threats": False,
        "operator_profile": {
            "enabled": True,
            "name": "Local Operator",
            "title": "System Administrator",
        },
        "accessibility": {
            "theme": "high_contrast",
            "density": "comfortable",
            "reduce_motion": True,
            "font_scale": 1.0,
        },
        "colors": {},
    }


class SnapshotContractTests(unittest.TestCase):
    def test_snapshot_is_json_safe_and_valid(self):
        snapshot = build_snapshot(
            sample_system(), ["[INFO] measured"], {"temp": "24C"},
            sample_router(2), {"status": "OK"}, {"active_file": "frame.jpg"},
            {"monitor_count": 1}, 10, False,
        )
        self.assertEqual([], validate_snapshot(snapshot))
        json.dumps(snapshot)
        self.assertEqual("ESTIMATED", snapshot["provenance"]["temperature"]["label"])
        self.assertEqual("MEASURED", snapshot["provenance"]["router"]["label"])

    def test_simulation_is_never_labeled_measured(self):
        snapshot = build_snapshot(
            sample_system(), [], None, None, None, None, None, 10, True,
        )
        self.assertEqual("SIMULATED", snapshot["provenance"]["telemetry"]["label"])
        self.assertEqual("SIMULATED", snapshot["provenance"]["radar"]["label"])


class DisplayTests(unittest.TestCase):
    @patch("core.display_info.detect_display_info")
    def test_auto_virtual_resolution_uses_full_monitor_arrangement(self, detect):
        detect.return_value = {
            "platform": "Windows",
            "primary": {"width": 1920, "height": 1080},
            "virtual": {"width": 3840, "height": 1080},
            "monitors": [{}, {}], "monitor_count": 2,
            "dpi": 144, "scale_percent": 150, "source": "test",
        }
        resolved, display = resolve_display_config({
            "resolution_width": "auto", "resolution_height": "auto",
            "display_mode": "virtual",
        })
        self.assertEqual((3840, 1080), (resolved["resolution_width"], resolved["resolution_height"]))
        self.assertEqual(2, display["monitor_count"])


@unittest.skipUnless(hasattr(CyberWallpaperGenerator, "generate_snapshot"), "renderer unavailable")
class WallpaperRenderTests(unittest.TestCase):
    def make_snapshot(self, router_count=24):
        return build_snapshot(
            sample_system(), ["[INFO] local event"],
            {"temp": "24°C", "condition": "Clear", "location": "Local",
             "humidity": "40%", "wind": "5 km/h", "feels_like": "24°C",
             "pressure": "1012 hPa", "uv_index": "2"},
            sample_router(router_count), {"status": "OK"},
            {"active_file": "N/A", "size_kb": 0}, {"monitor_count": 1}, 10,
        )

    def test_multi_resolution_output_sizes(self):
        for size in ((1366, 768), (1920, 1080), (1920, 1200), (2560, 1080)):
            with self.subTest(size=size):
                generator = CyberWallpaperGenerator(base_config(*size))
                image = generator.generate_snapshot(self.make_snapshot(), return_image=True)
                self.assertEqual(size, image.size)

    def test_dense_router_is_bounded_and_cache_is_reused(self):
        generator = CyberWallpaperGenerator(base_config())
        snapshot = self.make_snapshot(30)
        first = generator.generate_snapshot(snapshot, return_image=True)
        second = generator.generate_snapshot(snapshot, return_image=True)
        self.assertEqual((1920, 1080), first.size)
        self.assertEqual(first.size, second.size)
        stats = generator.cache_stats()
        self.assertGreaterEqual(stats["entries"], 5)
        self.assertGreaterEqual(stats["hits"], 5)
        self.assertLessEqual(generator.router_y2, 854)

    def test_key_panel_pixels_are_not_background(self):
        generator = CyberWallpaperGenerator(base_config())
        image = generator.generate_snapshot(self.make_snapshot(2), return_image=True)
        self.assertNotEqual(image.getpixel((22, 120)), generator.c_bg)
        self.assertNotEqual(image.getpixel((1298, 120)), generator.c_bg)
        self.assertNotEqual(image.getpixel((22, 562)), generator.c_bg)


if __name__ == "__main__":
    unittest.main()
