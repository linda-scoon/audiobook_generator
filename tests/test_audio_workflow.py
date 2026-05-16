import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import audio_workflow as aw
from ai_script_preparer import AIPreparationResult


class AudioWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.stories = self.root / "stories"
        self.story = self.stories / "silver-footfalls"
        for name in ("source", "chapters", "bible", "narration", "output", "logs"):
            (self.story / name).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_prepare_requires_explicit_mode(self):
        with self.assertRaises(aw.WorkflowError) as ctx:
            aw.require_mode(None, "prepare")
        self.assertIn("Preparation mode required", str(ctx.exception))

    def test_detects_prepared_script(self):
        text = "[NARRATOR]\nThe rain fell.\n\n[SFX: thunder]\n\n[ELENA: worried]\nWe should go.\n"
        detection = aw.detect_prepared_script(text)
        self.assertTrue(detection.prepared)
        self.assertGreaterEqual(detection.labelled_blocks, 3)

    def test_unprepared_mode_refuses_already_prepared_without_api_call(self):
        chapter = self.story / "chapters" / "chapter_001.md"
        chapter.write_text("[NARRATOR]\nThe rain fell.\n\n[ELENA]\nWe should go.\n", encoding="utf-8")
        story = aw.Story("silver-footfalls", self.story)
        with patch("audio_workflow.AIScriptPreparer.prepare") as mocked_prepare:
            with self.assertRaises(aw.WorkflowError):
                aw.prepare_story(story, "unprepared")
        mocked_prepare.assert_not_called()

    def test_auto_copies_prepared_without_api_call(self):
        chapter = self.story / "chapters" / "chapter_001.md"
        chapter.write_text("[NARRATOR]\nThe rain fell.\n\n[ELENA]\nWe should go.\n", encoding="utf-8")
        story = aw.Story("silver-footfalls", self.story)
        with patch("audio_workflow.AIScriptPreparer.prepare") as mocked_prepare:
            used_ai = aw.prepare_story(story, "auto")
        self.assertFalse(used_ai)
        mocked_prepare.assert_not_called()
        self.assertTrue((self.story / "narration" / "chapter_001_audio_script.md").exists())

    def test_unprepared_uses_ai_after_validation(self):
        chapter = self.story / "chapters" / "chapter_001.md"
        chapter.write_text("The rain fell. Elena said, We should go.", encoding="utf-8")
        story = aw.Story("silver-footfalls", self.story)
        result = AIPreparationResult(
            script="[NARRATOR]\nThe rain fell.\n\n[ELENA]\nWe should go.",
            provider="openai",
            model="test-model",
        )
        fake_preparer = Mock()
        fake_preparer.prepare.return_value = result
        with patch("audio_workflow.AIScriptPreparer", return_value=fake_preparer):
            used_ai = aw.prepare_story(story, "unprepared")
        self.assertTrue(used_ai)
        fake_preparer.prepare.assert_called_once_with("The rain fell. Elena said, We should go.")

    def test_generate_missing_script_has_good_error(self):
        story = aw.Story("silver-footfalls", self.story)
        with self.assertRaises(aw.WorkflowError) as ctx:
            aw.generate_story(story)
        self.assertIn("no prepared narration scripts", str(ctx.exception))

    def test_status_recommends_explicit_auto_prepare(self):
        (self.story / "chapters" / "chapter_001.md").write_text("Plain prose.", encoding="utf-8")
        story = aw.Story("silver-footfalls", self.story)
        statuses = aw.status_for_story(story)
        self.assertEqual(statuses[0].next_command, "audio prepare silver-footfalls --auto")


if __name__ == "__main__":
    unittest.main()
