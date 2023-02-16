"""
wordle_contexts.py
"""
import os
import json

import wordle_scraper

WORDLE_CONTEXTS = ["new_york_times", "wordlegame_org", "flappy_birdle"]

WORDLE_CONTEXTS_COMMON_NAME = {
    "new_york_times": "New York Times Wordle",
    "wordlegame_org": "wordlegame.org Wordle",
    "flappy_birdle": "Flappy Birdle"}

WORDLE_CONTEXTS_SCRAPER = {
    "new_york_times": wordle_scraper.scrap_nytimes,
    "wordlegame_org": wordle_scraper.scrap_wordlegame,
    "flappy_birdle": wordle_scraper.scrap_flappy_birdle}

WORDLE_CACHE = "cache"
WORDLE_SOLUTIONS_FILE_FORMAT = "solutions_{}.txt"
WORDLE_WORD_LIST_FILE_FORMAT = "word_list_{}.txt"
WORDLE_NAIVE_GUESSES_FILE_FORMAT = "naive_guesses_{}.json"
WORDLE_SMART_GUESSES_FILE_FORMAT = "smart_guesses_{}.json"

def get_contexts():
    return WORDLE_CONTEXTS

def get_common_name(context):
    return WORDLE_CONTEXTS_COMMON_NAME[context]

def load_solutions_word_list(context):
    # Check if word list exists
    solutions_file = os.path.join(
        WORDLE_CACHE, WORDLE_SOLUTIONS_FILE_FORMAT.format(context))
    word_list_file = os.path.join(
        WORDLE_CACHE, WORDLE_WORD_LIST_FILE_FORMAT.format(context))

    if os.path.isfile(solutions_file) and os.path.isfile(word_list_file):
        # Cache is present, load from cache
        with open(solutions_file) as f:
            solutions = [word.strip() for word in f]
        with open(word_list_file) as f:
            word_list = [word.strip() for word in f]

        # Verify results are valid
        wordle_scraper.check_solutions_word_lists(solutions, word_list)
        solutions.sort()
        word_list.sort()
    else:
        # Get results from internet
        solutions, word_list = WORDLE_CONTEXTS_SCRAPER[context]()

        # Verify results are valid
        wordle_scraper.check_solutions_word_lists(solutions, word_list)
        solutions.sort()
        word_list.sort()

        # Save results to cache
        if not os.path.exists(WORDLE_CACHE):
            os.mkdir(WORDLE_CACHE)

        with open(solutions_file, "w") as f:
            for word in solutions: f.write(word + "\n")
        with open(word_list_file, "w") as f:
            for word in word_list: f.write(word + "\n")

    return solutions, word_list

# def get_naive_guesses(context):
#     naive_file = os.path.join(
#         WORDLE_CACHE, WORDLE_NAIVE_GUESSES_FILE_FORMAT.format(context))
#     if os.path.isfile(naive_file):
#         with open(naive_file) as f:
#             return json.load(f)

# def set_naive_guesses(context, guesses):
#     naive_file = os.path.join(
#         WORDLE_CACHE, WORDLE_NAIVE_GUESSES_FILE_FORMAT.format(context))
#     with open(naive_file, "w") as f:
#         json.dump(guesses, f)

# def get_smart_guesses(context):
#     smart_file = os.path.join(
#         WORDLE_CACHE, WORDLE_SMART_GUESSES_FILE_FORMAT.format(context))
#     if os.path.isfile(smart_file):
#         with open(smart_file) as f:
#             return json.load(f)

# def set_smart_guesses(context, guesses):
#     smart_file = os.path.join(
#         WORDLE_CACHE, WORDLE_SMART_GUESSES_FILE_FORMAT.format(context))
#     with open(smart_file, "w") as f:
#         json.dump(guesses, f)

def load_guesses(context, naive):
    """Get the initial best guess for this context."""
    if naive:
        guesses_filename = WORDLE_NAIVE_GUESSES_FILE_FORMAT.format(context)
    else:
        guesses_filename = WORDLE_SMART_GUESSES_FILE_FORMAT.format(context)

    guesses_filename = os.path.join(WORDLE_CACHE, guesses_filename)

    # If opening file fails, silently fail to indicate results invalid
    try:
        with open(guesses_filename) as f:
            return json.load(f)
    except FileNotFoundError:
        pass

def save_guesses(context, naive, guesses):
    """Set the initial best guess for this context."""
    if naive:
        guesses_filename = WORDLE_NAIVE_GUESSES_FILE_FORMAT.format(context)
    else:
        guesses_filename = WORDLE_SMART_GUESSES_FILE_FORMAT.format(context)

    guesses_filename = os.path.join(WORDLE_CACHE, guesses_filename)
    with open(guesses_filename, "w") as f:
        json.dump(guesses, f)
