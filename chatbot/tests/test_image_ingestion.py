import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from app.rag.ingestion import _collect_local_image_docs, _collect_web_image_docs


class TestImageIngestion(unittest.TestCase):
    def test_collect_local_image_docs_fall_back_caption(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            image_file = tmp_path / "architecture.png"
            image_file.write_bytes(b"not-a-real-image")

            docs = _collect_local_image_docs(
                "![Architecture diagram](architecture.png)",
                tmp_path,
                "projectx",
            )

        self.assertEqual(len(docs), 1)
        self.assertIn("Image file: architecture.png", docs[0].page_content)
        self.assertIn("Caption: Architecture diagram.", docs[0].page_content)
        self.assertEqual(docs[0].metadata["project"], "projectx")
        self.assertEqual(docs[0].metadata["type"], "image")
        self.assertTrue(docs[0].metadata["has_image"])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test"})
    @patch("openai.OpenAI")
    def test_collect_local_image_docs_uses_vision_model_caption(self, mock_openai):
        mock_client = Mock()
        mock_response = Mock(
            output_text="Architecture diagram showing services and data flow."
        )
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            image_file = tmp_path / "architecture.png"
            image_file.write_bytes(b"not-a-real-image")

            docs = _collect_local_image_docs(
                "![Architecture diagram](architecture.png)",
                tmp_path,
                "projectx",
            )

        self.assertEqual(len(docs), 1)
        self.assertIn(
            "Vision caption: Architecture diagram showing services and data flow.",
            docs[0].page_content,
        )
        self.assertEqual(docs[0].metadata["vision_caption"], True)
        self.assertEqual(docs[0].metadata["caption_source"], "vision")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test"})
    @patch("openai.OpenAI")
    def test_collect_web_image_docs_uses_vision_model_caption(self, mock_openai):
        mock_client = Mock()
        mock_response = Mock(
            status_code=200,
            content=b"not-a-real-image",
            headers={"content-type": "image/png"},
        )
        mock_client.get.return_value = mock_response

        mock_ai_client = Mock()
        mock_ai_client.responses.create.return_value = Mock(
            output_text="Website architecture screenshot showing flow."
        )
        mock_openai.return_value = mock_ai_client

        soup = BeautifulSoup(
            '<html><body><img src="http://example.com/diagram.png" alt="Architecture diagram"></body></html>',
            "lxml",
        )
        docs = _collect_web_image_docs(
            soup, "http://example.com/page", "Example Page", mock_client
        )

        self.assertEqual(len(docs), 1)
        self.assertIn(
            "Vision caption: Website architecture screenshot showing flow.",
            docs[0].page_content,
        )
        self.assertEqual(docs[0].metadata["type"], "website_image")
        self.assertTrue(docs[0].metadata["vision_caption"])
        self.assertEqual(docs[0].metadata["caption_source"], "vision")


if __name__ == "__main__":
    unittest.main()
