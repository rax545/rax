import tempfile
import unittest
from pathlib import Path

from database import Database
from games import truth_or_dare
from hotness import boundary_signal, contains_explicit_marker, flirt_reply, hot_truth_or_dare
from mood import detect_mood
from relationship import conversation_deltas, relationship_stage


class CoreFeatureTests(unittest.TestCase):
    def test_mood_is_bilingual_and_style_aware(self):
        self.assertEqual(detect_mood("মন খারাপ লাগছে").mood, "sad")
        self.assertEqual(detect_mood("I am so happy!!!").mood, "joyful")
        self.assertEqual(detect_mood("deadline নিয়ে খুব stressed").mood, "stressed")

    def test_truth_or_dare_honours_mode(self):
        self.assertEqual(truth_or_dare("truth")[0], "truth")
        self.assertEqual(truth_or_dare("dare")[0], "dare")

    def test_profile_nickname_and_daily_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "luna.sqlite3"))
            database.initialize()
            database.set_nickname(7, 9, "Sunshine")
            mood = detect_mood("hello")
            friendship, affection = conversation_deltas(mood)
            for _ in range(3):
                database.record_conversation(
                    7,
                    9,
                    mood=mood.mood,
                    mood_confidence=mood.confidence,
                    friendship_delta=friendship,
                    affection_delta=affection,
                    daily_cap=2,
                )
            profile = database.get_relationship(7, 9)
            self.assertEqual(profile["nickname"], "Sunshine")
            self.assertEqual(profile["daily"]["event_count"], 3)
            self.assertLessEqual(profile["friendship_score"], friendship * 2)
            self.assertTrue(profile["daily"]["friendship_points"] <= friendship * 2)

    def test_relationship_stage_is_bounded(self):
        name, _, score = relationship_stage(100, 100)
        self.assertEqual(name, "Deep connection")
        self.assertEqual(score, 100)

    def test_hotness_requires_boundaries_and_stays_non_graphic(self):
        self.assertEqual(boundary_signal("too much, keep it normal"), "too much")
        self.assertIsNone(boundary_signal("give me a sweet compliment"))
        self.assertFalse(contains_explicit_marker(flirt_reply(level=3)))
        self.assertEqual(hot_truth_or_dare("truth", 3)[0], "truth")

    def test_hotness_preferences_are_scoped_and_resettable(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "luna.sqlite3"))
            database.initialize()
            database.set_age_confirmed(11, 22, True)
            database.set_hotness_level(11, 22, 3)
            database.set_hotness_enabled(11, 22, True)
            state = database.get_hotness(11, 22)
            self.assertEqual(state["level"], 3)
            self.assertEqual(state["enabled"], 1)
            self.assertEqual(database.get_hotness(12, 22)["enabled"], 0)
            database.set_hotness_boundary(11, 22, "soft")
            self.assertEqual(database.get_hotness(11, 22)["boundary_mode"], "soft")
            self.assertEqual(database.get_hotness(11, 22)["enabled"], 0)


if __name__ == "__main__":
    unittest.main()
