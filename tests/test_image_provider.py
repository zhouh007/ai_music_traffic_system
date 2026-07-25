import tempfile
import unittest
from pathlib import Path

from ai_music_system.models import ImageProviderConfig
from ai_music_system.providers.image.openai_compatible_provider import OpenAICompatibleImageProvider


class RecordingHttpClient:
    def __init__(self):
        self.calls = []

    def post_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"data": [{"b64_json": "aW1hZ2U="}]}


class ImageProviderTests(unittest.TestCase):
    def test_local_playground_proxy_uses_proxy_path_without_v1(self):
        client = RecordingHttpClient()
        config = ImageProviderConfig(
            name="codex2api",
            api_key="test-key",
            base_url="https://www.codex2api.com",
            api_proxy_url="http://127.0.0.1:4173/api-proxy",
            use_api_proxy=True,
        )
        provider = OpenAICompatibleImageProvider(config, client)

        with tempfile.TemporaryDirectory() as temp_dir:
            provider.generate_cover("test prompt", Path(temp_dir) / "cover.png")

        self.assertEqual(client.calls[0]["url"], "http://127.0.0.1:4173/api-proxy/images/generations")
        self.assertEqual(client.calls[0]["payload"]["n"], 1)

    def test_default_provider_keeps_openai_v1_endpoint(self):
        client = RecordingHttpClient()
        config = ImageProviderConfig(name="codex2api", api_key="test-key")
        provider = OpenAICompatibleImageProvider(config, client)

        with tempfile.TemporaryDirectory() as temp_dir:
            provider.generate_cover("test prompt", Path(temp_dir) / "cover.png")

        self.assertEqual(client.calls[0]["url"], "https://www.codex2api.com/v1/images/generations")


if __name__ == "__main__":
    unittest.main()
