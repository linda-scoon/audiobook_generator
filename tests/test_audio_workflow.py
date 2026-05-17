import os
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
        text = "[NARRATOR]\nThe rain fell.\n\n[SFX: thunder]\n\n[FMC: worried]\nWe should go.\n"
        detection = aw.detect_prepared_script(text)
        self.assertTrue(detection.prepared)
        self.assertGreaterEqual(detection.labelled_blocks, 3)

    def test_unprepared_mode_refuses_already_prepared_without_api_call(self):
        chapter = self.story / "chapters" / "chapter_001.md"
        chapter.write_text("[NARRATOR]\nThe rain fell.\n\n[FMC]\nWe should go.\n", encoding="utf-8")
        story = aw.Story("silver-footfalls", self.story)
        with patch("audio_workflow.AIScriptPreparer.prepare") as mocked_prepare:
            with self.assertRaises(aw.WorkflowError):
                aw.prepare_story(story, "unprepared")
        mocked_prepare.assert_not_called()

    def test_auto_copies_prepared_without_api_call(self):
        chapter = self.story / "chapters" / "chapter_001.md"
        chapter.write_text("[NARRATOR]\nThe rain fell.\n\n[FMC]\nWe should go.\n", encoding="utf-8")
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
            script="[NARRATOR]\nThe rain fell.\n\n[FMC]\nWe should go.",
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

    def test_generate_saves_audio_under_story_output(self):
        script = self.story / "narration" / "chapter_001_audio_script.md"
        script.write_text("[NARRATOR]\nRain fell.\n", encoding="utf-8")
        (self.root / "config").mkdir()
        aw.save_voice_roles({role: f"voice-{role.lower()}" for role in aw.REQUIRED_VOICE_ROLES}, self.root)
        story = aw.Story("silver-footfalls", self.story)

        with patch("audio_workflow.Path.cwd", return_value=self.root), patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test"}, clear=False):
            with patch("audio_workflow.elevenlabs_tts", return_value=b"mp3-bytes"):
                aw.generate_story(story)

        self.assertTrue((self.story / "output" / "chapter_001.mp3").exists())
        self.assertTrue((self.story / "output" / "chapter_001_metadata.json").exists())
        self.assertFalse((self.root / "output" / "silver-footfalls" / "chapter_001.mp3").exists())

    def test_status_recommends_explicit_auto_prepare(self):
        (self.story / "chapters" / "chapter_001.md").write_text("Plain prose.", encoding="utf-8")
        story = aw.Story("silver-footfalls", self.story)
        statuses = aw.status_for_story(story)
        self.assertEqual(statuses[0].next_command, "audio prepare silver-footfalls --auto")

    def test_unknown_character_label_is_rejected(self):
        script = self.story / "narration" / "chapter_001_audio_script.md"
        script.write_text("[NARRATOR]\nRain fell.\n\n[ELENA]\nGo now.\n", encoding="utf-8")
        with self.assertRaises(aw.WorkflowError) as ctx:
            aw.validate_prepared_script(script)
        self.assertIn("unknown speaker role", str(ctx.exception))

    def test_blank_voice_roles_stop_before_generation_request(self):
        script = self.story / "narration" / "chapter_001_audio_script.md"
        script.write_text("[NARRATOR]\nRain fell.\n", encoding="utf-8")
        (self.root / "config").mkdir()
        aw.save_voice_roles(aw.default_voice_roles(), self.root)
        story = aw.Story("silver-footfalls", self.story)
        with patch("audio_workflow.Path.cwd", return_value=self.root), patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test"}, clear=False):
            with patch("audio_workflow.elevenlabs_tts") as mocked_tts:
                with self.assertRaises(aw.WorkflowError) as ctx:
                    aw.generate_story(story)
        self.assertIn("blank ElevenLabs voice ID", str(ctx.exception))
        mocked_tts.assert_not_called()

    def test_auto_assign_preserves_existing_voice_ids(self):
        (self.root / "config").mkdir()
        roles = aw.default_voice_roles()
        roles["NARRATOR"] = "saved-narrator"
        aw.save_voice_roles(roles, self.root)
        voices = [{"voice_id": "female-1", "name": "Warm female", "labels": {"gender": "female"}}]
        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test"}, clear=False):
            with patch("audio_workflow.elevenlabs_list_voices", return_value=voices):
                aw.auto_assign_voice_roles(self.root)
        updated = aw.load_voice_roles(self.root)
        self.assertEqual(updated["NARRATOR"], "saved-narrator")
        self.assertEqual(updated["FMC"], "female-1")

    def test_load_env_file_reads_repo_dotenv_without_overwriting_shell(self):
        (self.root / ".env").write_text(
            "# local secrets\n"
            "ELEVENLABS_API_KEY=from-dotenv\n"
            "OPENAI_API_KEY=from-file # inline comment\n"
            "export ANTHROPIC_API_KEY='anthropic file key'\n",
            encoding="utf-8",
        )
        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "from-shell"}, clear=True):
            aw.load_env_file(self.root)
            self.assertEqual(os.environ["ELEVENLABS_API_KEY"], "from-shell")
            self.assertEqual(os.environ["OPENAI_API_KEY"], "from-file")
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "anthropic file key")

    def test_main_loads_dotenv_before_elevenlabs_voice_commands(self):
        (self.root / ".env").write_text("ELEVENLABS_API_KEY=from-dotenv\n", encoding="utf-8")
        voices = [{"voice_id": "voice-1", "name": "Dotenv voice"}]
        with patch("audio_workflow.Path.cwd", return_value=self.root), patch.dict("os.environ", {}, clear=True):
            with patch("audio_workflow.elevenlabs_list_voices", return_value=voices) as mocked_list:
                exit_code = aw.main(["voices", "list"])
        self.assertEqual(exit_code, 0)
        mocked_list.assert_called_once_with("from-dotenv")

    def test_preparation_prompt_file_is_loaded(self):
        from ai_script_preparer import load_preparation_prompt

        prompt = self.root / "prompt.md"
        prompt.write_text("Use role labels only.", encoding="utf-8")
        self.assertEqual(load_preparation_prompt(prompt), "Use role labels only.")


if __name__ == "__main__":
    unittest.main()
