"""Structural contracts shared by every social-publishing provider."""

from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from validation_pipeline.instagram_publication import DatabaseInstagramAuthority, LocalInstagramAuthority
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.social_publishing.contracts import PublicationAuthority, SocialPublisherAdapter
from validation_pipeline.social_publishing.providers.instagram import InstagramPublishingAdapter
from validation_pipeline.social_publishing.providers.tiktok import TikTokConfiguration, TikTokPublishingAdapter
from validation_pipeline.tiktok_publication import DatabaseTikTokAuthority, LocalTikTokAuthority


class SocialPublishingContractTests(unittest.TestCase):
    def test_both_local_and_database_authorities_implement_the_same_protocol(self) -> None:
        with TemporaryDirectory() as temporary:
            store = LocalBriefStore(Path(temporary))
            authorities = (
                LocalInstagramAuthority(store),
                LocalTikTokAuthority(store),
                DatabaseInstagramAuthority("postgresql://contract.invalid/database"),
                DatabaseTikTokAuthority("postgresql://contract.invalid/database"),
            )
            for authority in authorities:
                with self.subTest(authority=type(authority).__name__):
                    self.assertIsInstance(authority, PublicationAuthority)

    def test_both_provider_adapters_implement_the_same_protocol(self) -> None:
        instagram = InstagramPublishingAdapter(None, None, origin="")
        with TemporaryDirectory() as temporary:
            tiktok_authority = LocalTikTokAuthority(LocalBriefStore(Path(temporary)))
            tiktok = TikTokPublishingAdapter(tiktok_authority, TikTokConfiguration())
            for adapter in (instagram, tiktok):
                with self.subTest(provider=adapter.provider):
                    self.assertIsInstance(adapter, SocialPublisherAdapter)
                    self.assertIn(adapter.capabilities()["commit_strategy"], {
                        "after_transfer_ready", "on_transfer_create",
                    })


if __name__ == "__main__":
    unittest.main()
