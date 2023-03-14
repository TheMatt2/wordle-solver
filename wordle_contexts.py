"""
wordle_contexts.py
"""
import os
import json

ALL_WORDS_TOKEN = "ALL_WORDS_ARE_VALID_GUESSES"

import wordle_solver
import wordle_scraper

WORDLE_CONTEXT_IDS = [
    "new_york_times", "wordlegame_org", "wordplay_com", "wordlewebsite_com_daily",
    "wordlewebsite_com_unlimited", "absurdle", "flappy_birdle"]

WORDLE_CONTEXTS_NAME = {
    "new_york_times": "New York Times Wordle",
    "wordlegame_org": "wordlegame.org Wordle",
    "wordplay_com": "wordplay.com Wordle",
    "wordlewebsite_com_daily": "wordlewebsite.com Wordle (Daily)",
    "wordlewebsite_com_unlimited": 'wordlewebsite.com Wordle (Unlimited)',
    "absurdle": "Absurdle (https://qntm.org/files/absurdle/absurdle.html)",
    "flappy_birdle": "Flappy Birdle (https://flappybirdle.com)"}

WORDLE_CONTEXTS_SCRAPER = {
    "new_york_times": wordle_scraper.scrap_nytimes,
    "wordlegame_org": wordle_scraper.scrap_wordlegame,
    "wordplay_com": wordle_scraper.scrap_wordplay,
    "wordlewebsite_com_daily": wordle_scraper.scrap_wordlewebsite_daily,
    "wordlewebsite_com_unlimited": wordle_scraper.scrap_wordlewebsite_unlimited,
    "absurdle": wordle_scraper.scrap_absurdle,
    "flappy_birdle": wordle_scraper.scrap_flappy_birdle}

WORDLE_IS_ALL_WORDS = {"flappy_birdle": True}

WORDLE_CACHE = "cache"
WORDLE_SOLUTIONS_FILE_FORMAT = "solutions_{}.txt"
WORDLE_WORD_LIST_FILE_FORMAT = "word_list_{}.txt"
WORDLE_NAIVE_GUESSES_FILE_FORMAT = "naive_guesses_{}.json"
WORDLE_SMART_GUESSES_FILE_FORMAT = "smart_guesses_{}.json"

def load_words(filename):
    with open(filename) as f:
        words = []
        for word in f:
            if word:
                words.append(word.strip())
        return words

def save_words(words, filename):
    if words == ALL_WORDS_TOKEN:
        with open(filename, "w") as f:
            f.write(f"{ALL_WORDS_TOKEN}\n")
    else:
        # Save words normally
        words.sort()
        with open(filename, "w") as f:
            for word in words:
                f.write(f"{word}\n")

def ask_context():
    print("Please select a Wordle version to use:")
    for i in range(len(WORDLE_CONTEXT_IDS)):
        print(f"{i+1}) {WORDLE_CONTEXTS_NAME[WORDLE_CONTEXT_IDS[i]]}")

    # Have user choose wordle version
    while True:
        choice = input("Wordle version: ").strip()

        if not choice.isdigit():
            print(f"Invalid wordle version choice {choice!r}")
            continue

        choice = int(choice)
        if choice > len(WORDLE_CONTEXT_IDS):
            print(f"Invalid wordle version choice {choice!r}")
            continue

        context_id = WORDLE_CONTEXT_IDS[choice - 1]
        break

    # Ask for naive, if not all words
    if not WORDLE_IS_ALL_WORDS.get(context_id, False):
        naive = input("Naive Mode?: ").strip() == "y"
    else:
        naive = False

    return Context(context_id, naive)

class Context:
    """Context to control details of a Wordle game."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    word_length = 5

    def __init__(self, context_id, naive):
        self.context_id = context_id
        self.naive = naive
        self._solutions = None
        self._word_list = None
        self._guesses = None

    @property
    def name(self):
        return WORDLE_CONTEXTS_NAME[self.context_id]

    def _load_word_list_solutions(self):
        # Check if word list exists
        word_list_file = os.path.join(
            WORDLE_CACHE, WORDLE_WORD_LIST_FILE_FORMAT.format(self.context_id))
        solutions_file = os.path.join(
            WORDLE_CACHE, WORDLE_SOLUTIONS_FILE_FORMAT.format(self.context_id))

        if os.path.isfile(word_list_file) and os.path.isfile(solutions_file):
            # Cache is present, load from cache
            word_list = load_words(word_list_file)
            solutions = load_words(solutions_file)

            if word_list == [ALL_WORDS_TOKEN]:
                word_list = ALL_WORDS_TOKEN

            # Verify results are valid
            wordle_scraper.check_word_list_solutions(word_list, solutions, self)
            solutions.sort()
            if word_list != ALL_WORDS_TOKEN:
                word_list.sort()
        else:
            # Get results from internet
            print("Getting solutions and word list from internet.")
            word_list, solutions = WORDLE_CONTEXTS_SCRAPER[self.context_id]()

            # Verify results are valid
            wordle_scraper.check_word_list_solutions(word_list, solutions, self)
            solutions.sort()
            if word_list != ALL_WORDS_TOKEN:
                word_list.sort()

            # Save results to cache
            if not os.path.exists(WORDLE_CACHE):
                os.mkdir(WORDLE_CACHE)

            save_words(word_list, word_list_file)
            save_words(solutions, solutions_file)

        self._word_list = word_list
        self._solutions = solutions

    @property
    def word_list(self):
        if self._word_list is None:
            self._load_word_list_solutions()

        if self._word_list == ALL_WORDS_TOKEN:
            return AllWordsWordList(self)

        return self._word_list.copy()

    @property
    def solutions(self):
        if self._solutions is None:
            self._load_word_list_solutions()

        if self.naive:
            # In naive mode, solutions are all words
            return self.word_list.copy()
        else:
            return self._solutions.copy()

    def _load_guesses(self):
        """Get the initial best guess for this context."""
        if self.naive:
            guesses_filename = WORDLE_NAIVE_GUESSES_FILE_FORMAT.format(self.context_id)
        else:
            guesses_filename = WORDLE_SMART_GUESSES_FILE_FORMAT.format(self.context_id)

        guesses_filename = os.path.join(WORDLE_CACHE, guesses_filename)

        # If opening file fails, silently fail to indicate results invalid
        try:
            with open(guesses_filename) as f:
                return json.load(f)
        except FileNotFoundError:
            pass

    def _save_guesses(self, guesses):
        """Set the initial best guess for this context."""
        if self.naive:
            guesses_filename = WORDLE_NAIVE_GUESSES_FILE_FORMAT.format(self.context_id)
        else:
            guesses_filename = WORDLE_SMART_GUESSES_FILE_FORMAT.format(self.context_id)

        guesses_filename = os.path.join(WORDLE_CACHE, guesses_filename)
        with open(guesses_filename, "w") as f:
            json.dump(guesses, f)

    def get_initial_guesses(self):
        """Get the initial best guess for this context."""
        if self._guesses is not None:
            return guesses

        guesses = self._load_guesses()
        if not guesses:
            # Generate initial guesses
            guess_group = self.get_guess_group()
            solution_group = self.get_solution_group()

            rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group)
            self._save_guesses(guesses)

        return guesses

    def get_guess_group(self):
        if self.word_list == ALL_WORDS_TOKEN:
            return wordle_solver.AllWordsGuessGroup(self)
        else:
            return wordle_solver.GuessGroup(self.word_list, self)

    def get_solution_group(self):
        return wordle_solver.SolutionGroup(self.solutions, self)

class AllWordsWordList:
    """Special optimized object to represent all possible words are valid."""
    def __init__(self, context):
        self.context = context

    def __len__(self):
        return len(self.context.letters) ** self.context.word_length

    def __contains__(self, word):
        return len(word) == self.context.word_length
