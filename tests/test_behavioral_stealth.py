"""
Unit tests for BehavioralFingerprintSpoofer (Phase 1)
Tests pattern generation without browser — validates ranges and structure.
"""

import os
import sys
import unittest
import tempfile

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiktok.advanced_stealth import (
    BehavioralFingerprintSpoofer,
    BehavioralStatistics,
    PatternCache,
    PatternAnalytics,
    DemographicProfile,
    BehavioralPattern,
    DEMOGRAPHIC_PRESETS,
)


class TestDemographicPresets(unittest.TestCase):
    def test_all_presets_exist(self):
        expected = ["indonesia_teen_female", "indonesia_teen_male",
                    "indonesia_young_adult", "us_teen", "us_adult", "global_desktop"]
        for name in expected:
            self.assertIn(name, DEMOGRAPHIC_PRESETS)

    def test_preset_types(self):
        for name, profile in DEMOGRAPHIC_PRESETS.items():
            self.assertIsInstance(profile, DemographicProfile)
            self.assertTrue(profile.age_range)
            self.assertIn(profile.device_type, ("mobile", "desktop", "tablet"))


class TestBehavioralStatistics(unittest.TestCase):
    def test_engagement_rates(self):
        eng = BehavioralStatistics.get_engagement("indonesia_teen_female")
        self.assertGreater(eng["like"], 0)
        self.assertLess(eng["like"], 1)
        self.assertGreater(eng["comment"], 0)

    def test_session_duration(self):
        session = BehavioralStatistics.get_session("13-19")
        self.assertGreater(session["mean"], 0)
        self.assertGreater(session["std"], 0)

    def test_active_hours(self):
        hours = BehavioralStatistics.get_active_hours("13-19")
        self.assertEqual(len(hours), 24)
        self.assertTrue(all(0 <= h <= 1 for h in hours))

    def test_scroll_physics(self):
        scroll = BehavioralStatistics.get_scroll("mobile")
        self.assertIn("speed_range", scroll)
        self.assertEqual(len(scroll["speed_range"]), 2)

    def test_locale_data(self):
        loc = BehavioralStatistics.get_locale("ID")
        self.assertEqual(loc["tz"], "Asia/Jakarta")
        self.assertEqual(loc["lang"], "id-ID")

    def test_fallback_defaults(self):
        # Unknown keys should return defaults
        eng = BehavioralStatistics.get_engagement("nonexistent")
        self.assertIsInstance(eng, dict)
        loc = BehavioralStatistics.get_locale("ZZ")
        self.assertIsInstance(loc, dict)


class TestPatternCache(unittest.TestCase):
    def test_basic_cache(self):
        cache = PatternCache(max_size=10, ttl_seconds=60)
        pattern = BehavioralPattern(demographic="test")
        cache.put("test_demo", "evening", pattern)
        result = cache.get("test_demo", "evening")
        self.assertIsNotNone(result)
        self.assertEqual(result.demographic, "test")

    def test_cache_miss(self):
        cache = PatternCache()
        result = cache.get("nonexistent", "morning")
        self.assertIsNone(result)

    def test_lru_eviction(self):
        cache = PatternCache(max_size=3, ttl_seconds=3600)
        for i in range(5):
            cache.put(f"demo_{i}", "evening", BehavioralPattern(demographic=f"d{i}"))
        self.assertLessEqual(cache.size, 3)

    def test_size_property(self):
        cache = PatternCache()
        self.assertEqual(cache.size, 0)
        cache.put("a", "b", BehavioralPattern())
        self.assertEqual(cache.size, 1)


class TestPatternAnalytics(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.analytics = PatternAnalytics(self.tmpfile.name)

    def tearDown(self):
        try:
            os.unlink(self.tmpfile.name)
        except:
            pass

    def test_record_and_query(self):
        self.analytics.record_usage("key1", "test_demo", True, "evening", "test")
        self.analytics.record_usage("key1", "test_demo", True, "evening", "test")
        self.analytics.record_usage("key2", "test_demo", False, "morning", "test")
        rate = self.analytics.get_success_rate("test_demo")
        self.assertAlmostEqual(rate, 2/3, places=2)

    def test_best_patterns(self):
        for _ in range(5):
            self.analytics.record_usage("good", "demo", True)
        for _ in range(5):
            self.analytics.record_usage("bad", "demo", False)
        best = self.analytics.get_best_patterns("demo", limit=2)
        self.assertEqual(len(best), 2)
        self.assertEqual(best[0]["key"], "good")

    def test_effectiveness_report(self):
        self.analytics.record_usage("k", "demo_a", True)
        self.analytics.record_usage("k", "demo_b", False)
        report = self.analytics.get_effectiveness_report()
        self.assertIn("demo_a", report)
        self.assertIn("demo_b", report)


if __name__ == "__main__":
    unittest.main()
