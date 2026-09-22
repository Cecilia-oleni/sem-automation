import unittest

from sem_automation.reporting.angel_yeast.dataset import (
    build_processed_data,
    categorize,
    country_map_from_geo_regions,
    conversion_total,
    load_config,
    month_range,
    previous_month,
    resolve_country,
)


class DirectMonthlyReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def test_month_ranges(self):
        august = month_range("2026-08")
        self.assertEqual(august.start, "2026-08-01")
        self.assertEqual(august.end, "2026-08-31")
        self.assertEqual(previous_month("2026-01"), "2025-12")

    def test_brand_has_highest_category_priority(self):
        category = categorize(
            "S-brand品牌", "S-YE/Raising Agent+brand", self.config
        )
        self.assertEqual(category, "brand")

    def test_category_rules_from_reference_image(self):
        cases = [
            ("Y-CIS& Main product", "Y-CIS-Baking Yeast-product&sales", "Baking Yeast"),
            ("S-brewing", "S-Brewing Yeast-2B/C", "Brewing Yeast"),
            ("S-others", "S-Animal Nutrition", "Animal Nutrition"),
            ("S-others", "S-Biotechnology Yeast-product", "Biotechnology Yeast"),
            ("S-others", "S-Raising Agent", "Raising Agent"),
            ("S-YE", "S-YE-product", "YE"),
        ]
        for campaign, adgroup, expected in cases:
            with self.subTest(adgroup=adgroup):
                self.assertEqual(categorize(campaign, adgroup, self.config), expected)

    def test_conversion_total_uses_only_configured_goals(self):
        row = {"Conversions_438461092_AUTO": 2, "Conversions_438463889_AUTO": 3}
        row["Conversions_999999999_AUTO"] = 100
        self.assertEqual(conversion_total(row, self.config), 5)

    def test_country_resolution_uses_parent_names(self):
        self.assertEqual(
            resolve_country(["Moscow", "Russia", "Europe"], self.config["known_countries"]),
            "Russia",
        )
        self.assertEqual(
            resolve_country(["Unknown"], self.config["known_countries"]), "Others"
        )

    def test_country_map_walks_parent_ids(self):
        regions = [
            {"GeoRegionId": 225, "GeoRegionName": "Russia", "GeoRegionType": "Country", "ParentId": 10001},
            {"GeoRegionId": 3, "GeoRegionName": "Central Federal District", "GeoRegionType": "District", "ParentId": 225},
            {"GeoRegionId": 213, "GeoRegionName": "Moscow", "GeoRegionType": "City", "ParentId": 3},
        ]
        self.assertEqual(country_map_from_geo_regions(regions, [213]), {"213": "Russia"})

    def test_country_map_supports_client_reporting_override_roots(self):
        regions = [
            {"GeoRegionId": 977, "GeoRegionName": "Republic of Crimea", "GeoRegionType": "Region", "ParentId": None},
            {"GeoRegionId": 146, "GeoRegionName": "Simferopol", "GeoRegionType": "City", "ParentId": 977},
        ]
        result = country_map_from_geo_regions(
            regions, [146], root_country_overrides={"977": "Russia"}
        )
        self.assertEqual(result, {"146": "Russia"})

    def test_processed_keyword_top_lists(self):
        goal_field = "Conversions_438461092_AUTO"
        empty = {key: [] for key in ["account", "network", "campaign", "geo", "criteria", "adgroup"]}
        empty["account"] = [
            {"Month": "2026-07-01", "Impressions": 1, "Clicks": 1, "Cost": 1, goal_field: 0},
            {"Month": "2026-08-01", "Impressions": 2, "Clicks": 2, "Cost": 2, goal_field: 1},
        ]
        empty["criteria"] = [
            {
                "Month": "2026-08-01",
                "CampaignName": "S-baking",
                "AdGroupName": "S-Baking Yeast-product",
                "Criterion": "дрожжи активные купить",
                "Clicks": 10,
                "Impressions": 100,
                "Cost": 5,
                goal_field: 1,
            }
        ]
        result = build_processed_data(
            empty, self.config, "2026-08", {}, translate_keywords=False
        )
        self.assertEqual(result["top_clicks"][0]["ChineseKeyword"], "购买活性酵母")
        self.assertEqual(result["top_conversions"][0]["ConversionsTotal"], 1)


if __name__ == "__main__":
    unittest.main()
