import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class FakeChatAgent:
    def __init__(self):
        self.messages = None
        self._sources = [
            {
                "content": "Oswald is a portfolio author.",
                "metadata": {"title": "About Oswald"},
            }
        ]

    def clear_sources(self):
        self._sources = []

    async def ainvoke(self, inputs):
        self.messages = inputs.get("messages")
        self._sources = [
            {
                "content": "Oswald is a portfolio author.",
                "metadata": {"title": "About Oswald"},
            }
        ]
        return {
            "messages": [
                SimpleNamespace(
                    content="Oswald is a software engineer who builds portfolio projects.",
                    tool_calls=[{"name": "search_about_me"}],
                )
            ]
        }

    def get_sources(self):
        return self._sources


class TestApiRoutes(unittest.TestCase):
    @patch("app.api.routes._agent")
    def test_chat_endpoint_preserves_history_and_returns_sources(
        self, mock_agent_factory
    ):
        fake_agent = FakeChatAgent()
        mock_agent_factory.return_value = fake_agent

        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Who is Oswald?",
                "history": [
                    {"role": "user", "content": "Tell me about Oswald's background."}
                ],
                "session_id": "session-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(
            payload["answer"],
            "Oswald is a software engineer who builds portfolio projects.",
        )
        self.assertEqual(payload["session_id"], "session-123")
        self.assertIn("search_about_me", payload["tool_calls"])
        self.assertEqual(payload["sources"][0]["metadata"]["title"], "About Oswald")

        self.assertIsNotNone(fake_agent.messages)
        self.assertEqual(len(fake_agent.messages), 2)
        self.assertTrue(
            fake_agent.messages[0].content.startswith("Tell me about Oswald")
        )
        self.assertTrue(fake_agent.messages[1].content.startswith("User query:"))


if __name__ == "__main__":
    unittest.main()
