import unittest

from app.prompts import build_system_prompt


class TestPrompts(unittest.TestCase):
    def test_build_system_prompt_returns_text(self):
        p = build_system_prompt()
        self.assertIsInstance(p, str)
        self.assertGreater(len(p.strip()), 0, "System prompt should not be empty")


if __name__ == "__main__":
    unittest.main()
