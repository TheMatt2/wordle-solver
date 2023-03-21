"""
wordle_contexts.py
"""
import os
import hjson
import filelock

ALL_WORDS_TOKEN = "ALL_WORDS_ARE_VALID_GUESSES"

import wordle_solver
import wordle_scraper

from wordle_utils import sortdict

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

WORDLE_CONTEXTS_IS_ALL_WORDS = {"flappy_birdle": True}
WORDLE_CONTEXTS_WORD_LENGTHS = {"wordlegame_org": [4, 11]}

WORDLE_CACHE = "cache"
WORDLE_WORD_LIST_FILE_FORMAT = "word_list_{context_id}.txt"
WORDLE_SOLUTIONS_FILE_FORMAT = "solutions_{context_id}.txt"
WORDLE_GUESSES_FILE_FORMAT = "guesses_{naive}_{context_id}_{word_length:d}.json"

def load_words(filename):
    with open(filename) as f:
        words = []
        for word in f:
            if word:
                words.append(word.strip())
        return words

def save_words(words, filename):
    words.sort()
    with open(filename, "w") as f:
        for word in words:
            f.write(f"{word}\n")

def ask_context():
    print("Please select a Wordle Version to use:")
    for i in range(len(WORDLE_CONTEXT_IDS)):
        print(f"{i+1}) {WORDLE_CONTEXTS_NAME[WORDLE_CONTEXT_IDS[i]]}")

    # Have user choose wordle version
    while True:
        choice = input("Wordle Version: ").strip()

        if not choice.isdigit():
            print(f"Invalid Wordle Version Choice {choice!r}")
            continue

        choice = int(choice)
        if choice > len(WORDLE_CONTEXT_IDS):
            print(f"Invalid Wordle Version Choice {choice!r}")
            continue

        context_id = WORDLE_CONTEXT_IDS[choice - 1]
        break

    # Ask for word length, if in question
    word_length = WORDLE_CONTEXTS_WORD_LENGTHS.get(context_id, 5)

    if not isinstance(word_length, int):
        # Choose from multiple word length
        word_min, word_max = word_length

        while True:
            choice = input(f"Word Length [{word_min}, {word_max}]: ").strip()

            if not choice.isdigit():
                print(f"Invalid Word Length {choice!r}")
                continue

            choice = int(choice)
            if not word_min <= choice <= word_max:
                print(f"Invalid Word Length {choice!r}")
                continue

            word_length = choice
            break

    # Ask for naive, if not all words
    if not WORDLE_CONTEXTS_IS_ALL_WORDS.get(context_id, False):
        naive = input("Naive Mode?: ").strip() == "y"
    else:
        naive = False

    return Context(context_id, naive, word_length)

def get_all_contexts():
    """Generate all supported contexts."""
    for context_id in WORDLE_CONTEXT_IDS:
        for naive in [False, True]:
            if naive and WORDLE_CONTEXTS_IS_ALL_WORDS.get(context_id):
                # All words can not be naive
                continue

            length = WORDLE_CONTEXTS_WORD_LENGTHS.get(context_id, 5)
            if not isinstance(length, int):
                # Multiple lengths
                min_length, max_length = length
                for length in range(min_length, max_length):
                    yield Context(context_id, naive, length)
            else:
                yield Context(context_id, naive, length)

class Context:
    """Context to control details of a Wordle game."""
    letters = "abcdefghijklmnopqrstuvwxyz"

    def __init__(self, context_id, naive = False, word_length = None):
        """Create context to descript a wordle game.
        If word length is None, word length is infered from context.
        """
        self.context_id = context_id

        # Naive is only valid if word list is not all words
        if naive and context_id in WORDLE_CONTEXTS_IS_ALL_WORDS:
            raise ValueError("Naive is not valid for all words context")

        self.naive = naive

        if word_length is None:
            # Try to infer word length
            word_length = WORDLE_CONTEXTS_WORD_LENGTHS.get(context_id, 5)
            if not isinstance(word_length, int):
                raise ValueError(f"Unable to infer word length for context {context_id}")

        self.word_length = word_length

        self._word_list = None
        self._solutions = None

        # Track for loading and saving to cache
        self._words_guessed = []
        self._cache_data = None

    def reset(self):
        """Reset the turn of the context."""
        self._words_guessed = []

    def next_turn(self, word, result):
        """Add a word and result to move to next turn."""
        self._words_guessed.append((word, result))

    @property
    def name(self):
        return WORDLE_CONTEXTS_NAME[self.context_id]

    @property
    def turns(self):
        return len(self._words_guessed)

    def _load_word_list_solutions(self):
        # Check if word list exists
        word_list_file = WORDLE_WORD_LIST_FILE_FORMAT.format(context_id = self.context_id)
        solutions_file = WORDLE_SOLUTIONS_FILE_FORMAT.format(context_id = self.context_id)

        word_list_file = os.path.join(WORDLE_CACHE, word_list_file)
        solutions_file = os.path.join(WORDLE_CACHE, solutions_file)

        if os.path.isfile(word_list_file) and os.path.isfile(solutions_file):
            # Cache is present, load from cache
            word_list = load_words(word_list_file)
            solutions = load_words(solutions_file)

            # Verify results are valid
            self._check_word_list_solutions(word_list, solutions)
        else:
            # Get results from internet
            print("Getting solutions and word list from internet.")
            word_list, solutions = WORDLE_CONTEXTS_SCRAPER[self.context_id]()

            # Verify words are valid
            self._check_word_list_solutions(word_list, solutions)

            if word_list != [ALL_WORDS_TOKEN]:
                word_list.sort()
            solutions.sort()

            # Save results to cache
            if not os.path.exists(WORDLE_CACHE):
                os.mkdir(WORDLE_CACHE)

            save_words(word_list, word_list_file)
            save_words(solutions, solutions_file)

        # Restrict word list and solutions to only words that match word length
        if word_list != [ALL_WORDS_TOKEN]:
            word_list = [word for word in word_list if len(word) == self.word_length]
        self._word_list = word_list

        solutions = [word for word in solutions if len(word) == self.word_length]
        self._solutions = solutions

    def _check_words(self, words):
        # Verify words are the character set
        for word in words:
            for c in word:
                if c not in self.letters:
                    raise ValueError(f"{word!r} has illegal letter {c!r}")

    def _check_word_list_solutions(self, word_list, solutions):
        # Verify solution and word lists make sense
        # Make into sets and check lengths
        word_list_count = len(word_list)
        word_list = set(word_list)
        if len(word_list) != word_list_count:
            raise ValueError("Word list contains duplicate words")

        solutions_count = len(solutions)
        solutions = set(solutions)
        if len(solutions) != solutions_count:
            raise ValueError("Solutions contain duplicate words")

        # Check solutions first
        self._check_words(solutions)

        if word_list != set([ALL_WORDS_TOKEN]):
            self._check_words(word_list)

            # Check that all solutions are in word list
            if not word_list.issuperset(solutions):
                raise ValueError("Not all solutions are in word list")

    def _guesses_filename(self):
        naive_str = "naive" if self.naive else "smart"
        guesses_filename = WORDLE_GUESSES_FILE_FORMAT.format(
            naive = naive_str, context_id = self.context_id, word_length = self.word_length)

        guesses_filename = os.path.join(WORDLE_CACHE, guesses_filename)
        return guesses_filename

    def _load_guess_data(self):
         if self._cache_data is None:
            # If tempfile exists, refuse to load
            tmpfile = f"{self._guesses_filename()}.tmp"
            if os.path.exists(tmpfile):
                raise FileExistsError("Temp file exists for cache. Something is wrong.")

            # Try to load cache
            try:
                with open(self._guesses_filename()) as f:
                    self._cache_data = hjson.load(f)
            except FileNotFoundError:
                self._cache_data = {}

    def _save_guess_data(self):
        # Dump first to a temp file, to avoid half writing the cache
        # Because it turns out safely writing file is hard
        tmpfile = f"{self._guesses_filename()}.tmp"
        with open(tmpfile, "w") as f:
            hjson.dumpJSON(self._cache_data, f, indent = "\t")

        # Move temp file to actual file
        os.replace(tmpfile, self._guesses_filename())

    def load_guesses(self):
        """Get the best guess for this turn."""
        # Return cache data, for the particular words guessed
        with filelock.FileLock(f"{self._guesses_filename()}.lck", timeout = 15):
            self._load_guess_data()

        cache_data = self._cache_data
        for word, result in self._words_guessed:
            # Attempt to traverse to the point in the cache
            # with guess for these series of words
            try:
                cache_data = cache_data[word]["next_turn"][result]
            except KeyError:
                return None, [], []

        # Use guesses if present
        rank = None
        guesses = []
        foils = []
        for guess, data in cache_data.items():
            if rank is None:
                rank = data["rank"]
            else:
                if rank != data["rank"]:
                    raise ValueError("Guesses have different ranks")

            guesses.append(guess)
            foils.append(data["foil"])

        return rank, guesses, foils

    def _save_guesses_internal(self, rank, guesses, foils):
        """Save guesses into the cache, does not write to disk."""
        cache_data = self._cache_data
        for word, result in self._words_guessed:
            # Attempt to traverse to the point in the cache
            # with guess for these series of words
            if word in cache_data:
                if result not in cache_data[word].setdefault("next_turn", {}):
                    cache_data[word]["next_turn"][result] = {}

                    # Make sure results are sorted
                    cache_data[word]["next_turn"] = sortdict(
                        cache_data[word]["next_turn"], key = wordle_solver._result_key)

                cache_data = cache_data[word]["next_turn"][result]
            else:
                return

        # Add guesses to cache (replacing existing)
        cache_data.clear()

        # Make sure guesses are added in alphabetical order
        for guess, foil in sorted(zip(guesses, foils)):
            cache_data[guess] = {
                "rank": rank,
                "foil": foil,
            }

    def save_guesses(self, rank, guesses, foils):
        """Save guesses into the cache."""
        # Do not save guesses further than 1 turn
        if len(self._words_guessed) > 1:
            return

        # Make sure cache is loaded, use file lock to prevent collisions
        with filelock.FileLock(f"{self._guesses_filename()}.lck", timeout = 15):
            self._cache_data = None # purge to force reload
            self._load_guess_data()
            self._save_guesses_internal(rank, guesses, foils)
            self._save_guess_data()

    def get_word_list(self):
        if self._word_list is None:
            self._load_word_list_solutions()
        return self._word_list.copy()

    def get_solutions(self):
        if self._solutions is None:
            self._load_word_list_solutions()

        if self.naive:
            return self._word_list.copy()
        else:
            return self._solutions.copy()

    def get_guess_group(self):
        if self._word_list is None:
            self._load_word_list_solutions()

        if self._word_list == [ALL_WORDS_TOKEN]:
            return wordle_solver.AllWordsGuessGroup(self)
        else:
            return wordle_solver.GuessGroup(self._word_list, self)

    def get_solution_group(self):
        if self._solutions is None:
            self._load_word_list_solutions()

        if self.naive:
            return wordle_solver.SolutionGroup(self._word_list, self)
        else:
            return wordle_solver.SolutionGroup(self._solutions, self)

    def is_valid_word(self, word):
        if self._word_list is None:
            self._load_word_list_solutions()

        if self._word_list == [ALL_WORDS_TOKEN]:
            return len(word) == self.word_length
        return word in self._word_list
