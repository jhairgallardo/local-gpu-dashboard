import os
import unittest
from unittest.mock import patch

from app import main, runtime_config


PROCESS_PAYLOAD = {
    "count": 1,
    "items": [
        {
            "pid": 123,
            "types": ["compute"],
            "gpu_memory_mib": 1024.0,
            "name": "python",
            "username": "jhair",
            "status": "running",
            "command_line": "python train.py --epochs 10",
            "detail_unavailable": [],
        }
    ],
    "unavailable_sources": [],
}


class RuntimeConfigTests(unittest.TestCase):
    def test_privacy_config_defaults_to_visible_process_fields(self):
        config = runtime_config.get_privacy_config(env={})

        self.assertEqual(
            config,
            {
                "show_process_details": True,
                "show_command_lines": True,
                "show_usernames": True,
            },
        )

    def test_command_line_and_username_redaction_keep_process_rows(self):
        config = runtime_config.get_privacy_config(
            env={
                "SHOW_COMMAND_LINES": "0",
                "SHOW_USERNAMES": "0",
            }
        )

        redacted = runtime_config.apply_process_privacy(PROCESS_PAYLOAD, config)

        self.assertTrue(redacted["redacted"])
        self.assertEqual(redacted["redacted_fields"], ["command_line", "username"])
        self.assertEqual(redacted["count"], 1)
        self.assertEqual(len(redacted["items"]), 1)

        process = redacted["items"][0]
        self.assertIsNone(process["command_line"])
        self.assertIsNone(process["username"])
        self.assertEqual(process["redacted_fields"], ["command_line", "username"])
        reasons = {
            detail["field"]: detail["reason"]
            for detail in process["detail_unavailable"]
        }
        self.assertEqual(reasons["command_line"], "Redacted by SHOW_COMMAND_LINES=0.")
        self.assertEqual(reasons["username"], "Redacted by SHOW_USERNAMES=0.")

    def test_process_detail_redaction_removes_items_but_preserves_count(self):
        config = runtime_config.get_privacy_config(env={"SHOW_PROCESS_DETAILS": "0"})

        redacted = runtime_config.apply_process_privacy(PROCESS_PAYLOAD, config)

        self.assertTrue(redacted["redacted"])
        self.assertEqual(redacted["redacted_fields"], ["processes"])
        self.assertEqual(redacted["count"], 1)
        self.assertEqual(redacted["items"], [])
        self.assertIn("SHOW_PROCESS_DETAILS=0", redacted["redaction_reason"])

    def test_demo_api_snapshot_applies_runtime_redaction(self):
        env = {
            "DEMO_MODE": "1",
            "SHOW_PROCESS_DETAILS": "1",
            "SHOW_COMMAND_LINES": "0",
            "SHOW_USERNAMES": "0",
        }
        with patch.dict(os.environ, env):
            snapshot = main.api_snapshot()

        process_payload = snapshot["gpus"][0]["processes"]
        process = process_payload["items"][0]
        self.assertTrue(process_payload["redacted"])
        self.assertIsNone(process["command_line"])
        self.assertIsNone(process["username"])

    def test_demo_api_can_hide_all_process_details(self):
        env = {
            "DEMO_MODE": "1",
            "SHOW_PROCESS_DETAILS": "0",
            "SHOW_COMMAND_LINES": "1",
            "SHOW_USERNAMES": "1",
        }
        with patch.dict(os.environ, env):
            snapshot = main.api_snapshot()
            diagnostics = main.api_diagnostics()

        process_payload = snapshot["gpus"][0]["processes"]
        self.assertGreater(process_payload["count"], 0)
        self.assertEqual(process_payload["items"], [])
        self.assertEqual(process_payload["redacted_fields"], ["processes"])
        self.assertFalse(
            diagnostics["runtime_config"]["privacy"]["show_process_details"]
        )


if __name__ == "__main__":
    unittest.main()
