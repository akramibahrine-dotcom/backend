from app.services.traffic_source import derive_traffic_platform, platform_to_utm_source


class TestDeriveTrafficPlatform:
    def test_tiktok_from_click_id(self):
        assert derive_traffic_platform(ttclid="abc123") == "TikTok"

    def test_meta_from_fbclid_in_url(self):
        assert derive_traffic_platform(
            landing_page_url="https://baytseha.shop/products/fertility-tea?fbclid=IwAR123"
        ) == "Meta"

    def test_snapchat_from_sc_cid(self):
        assert derive_traffic_platform(
            landing_page_url="https://baytseha.shop/?ScCid=xyz"
        ) == "Snapchat"

    def test_utm_source_tiktok(self):
        assert derive_traffic_platform(utm_source="tiktok", utm_medium="paid") == "TikTok"

    def test_direct_when_no_signals(self):
        assert derive_traffic_platform() == "Direct"

    def test_platform_to_utm_source(self):
        assert platform_to_utm_source("TikTok") == "tiktok"
        assert platform_to_utm_source("Meta") == "facebook"
