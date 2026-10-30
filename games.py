"""Safe, lightweight couple-game content for Luna."""

from __future__ import annotations

import random
from typing import TypedDict


TRUTHS: tuple[str, ...] = (
    "কোন ছোট্ট জিনিসটা আজ তোমাকে হাসিয়েছে?",
    "তোমার ideal chill day কেমন দেখতে?",
    "Luna-র কোন habit তোমার সবচেয়ে funny লাগে?",
    "কোন গানটা তোমার current mood-এর সঙ্গে মিলে যায়?",
    "তুমি বন্ধুত্বে কোন গুণটাকে সবচেয়ে বেশি value করো?",
    "সম্প্রতি নিজের কোন কাজ নিয়ে তুমি একটু proud?",
    "কোন harmless guilty pleasure তুমি লুকাও না?",
    "কোন জায়গায় একদিন ঘুরতে যেতে চাও?",
    "কেউ মন খারাপ করলে তাকে comfort করার তোমার favourite way কী?",
    "আজকের দিনের একটিমাত্র memory save করতে হলে কোনটা করতে?",
)

DARES: tuple[str, ...] = (
    "৩০ সেকেন্ডের জন্য তোমার favourite song-এর chorus গুনগুন করো—না চাইলে শুধু lyrics লিখে দাও।",
    "তোমার আশেপাশে থাকা কোনো নীল জিনিসের একটি creative নাম দাও।",
    "Luna-কে তিনটি silly emoji দিয়ে তোমার mood বোঝাও।",
    "এক গ্লাস পানি খেয়ে ফিরে এসে একটি positive word লিখো।",
    "তোমার next message-এ একটি harmless tongue-twister ব্যবহার করো।",
    "তোমার আজকের mood-এর জন্য একটি movie title বানাও।",
    "তিনটি শব্দে নিজের আজকের দিন describe করো।",
    "কাছের কাউকে একটি ছোট্ট genuine compliment দাও—তবে pressure নয়।",
    "এক মিনিট screen থেকে চোখ সরিয়ে stretch করো, তারপর ready হলে ফিরে এসো।",
    "একটি imaginary café-এর নাম এবং signature drink বানাও।",
)


class QuizQuestion(TypedDict):
    id: str
    question: str
    choices: list[str]
    answer: int
    explanation: str


QUIZ_QUESTIONS: tuple[QuizQuestion, ...] = (
    {
        "id": "comfort",
        "question": "কেউ tired বললে Luna-র প্রথম response কী হওয়া উচিত?",
        "choices": ["আরও কাজ দাও", "শুনে নরমভাবে support করা", "ignore করা", "roast করা"],
        "answer": 1,
        "explanation": "শোনা, pressure না দেওয়া, আর rest-এর কথা মনে করানোই caring response।",
    },
    {
        "id": "water",
        "question": "দীর্ঘ gaming session-এ কোনটি ভালো habit?",
        "choices": ["পানি ও ছোট break", "সারারাত জেগে থাকা", "খাবার বাদ দেওয়া", "সব notification বাড়ানো"],
        "answer": 0,
        "explanation": "পানি, চোখের বিরতি এবং rest—সবই healthy gaming-এর অংশ।",
    },
    {
        "id": "conversation",
        "question": "ভালো conversation-এর সবচেয়ে দরকারি অংশ কোনটি?",
        "choices": ["শুধু নিজের কথা", "জিততেই হবে", "মন দিয়ে শোনা", "reply না দেওয়া"],
        "answer": 2,
        "explanation": "শোনা ও একে অপরের সীমাকে সম্মান করা connection-কে meaningful করে।",
    },
    {
        "id": "luna",
        "question": "Luna-র relationship level কোন জিনিসের game-like summary?",
        "choices": ["বাস্তব commitment", "কথা ও game participation", "bank balance", "server rank"],
        "answer": 1,
        "explanation": "এটি কথোপকথন ও game participation-এর একটি fictional progress meter, বাস্তব commitment নয়।",
    },
    {
        "id": "consent",
        "question": "Truth or Dare-এ uncomfortable prompt এলে কী করা যাবে?",
        "choices": ["skip করা", "জোর করা", "private info প্রকাশ করা", "unsafe কাজ করা"],
        "answer": 0,
        "explanation": "যে কোনো prompt skip বা পরিবর্তন করা সবসময় ঠিক আছে।",
    },
)


def truth_or_dare(mode: str = "random") -> tuple[str, str]:
    """Return ``(kind, prompt)`` for a safe random prompt."""

    mode = (mode or "random").lower()
    if mode not in {"truth", "dare", "random"}:
        mode = "random"
    kind = random.choice(("truth", "dare")) if mode == "random" else mode
    prompt = random.choice(TRUTHS if kind == "truth" else DARES)
    return kind, prompt


def random_quiz() -> QuizQuestion:
    """Return a copy so a view cannot mutate the shared question bank."""

    question = random.choice(QUIZ_QUESTIONS)
    return {
        "id": question["id"],
        "question": question["question"],
        "choices": list(question["choices"]),
        "answer": question["answer"],
        "explanation": question["explanation"],
    }
