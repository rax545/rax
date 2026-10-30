import tempfile
import unittest
from pathlib import Path

from database import Database
from games import truth_or_dare
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


if __name__ == "__main__":
    unittest.main()
