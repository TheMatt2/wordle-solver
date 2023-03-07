"""
wordle_scraper.py

Manage word lists and solution sets for Wordle games.

Two Wordle Games are currently supported:
 - https://wordlegame.org
 - https://www.nytimes.com/games/wordle
"""
import json
import requests
import itertools
import urllib.parse

from wordle_contexts import ALL_WORDS_TOKEN, LETTERS, WORD_LENGTH

def check_solutions_word_lists(solutions, word_list):
    # Verify solution and word lists make sense
    if word_list != ALL_WORDS_TOKEN:
        words = itertools.chain(solutions, word_list)
    else:
        # Don't bother checking word list
        words = solutions

    for word in words:
        if len(word) != WORD_LENGTH:
            raise ValueError(f"{word!r} is not {WORD_LENGTH} letters: ")

        for c in word:
            if c not in LETTERS:
                raise ValueError(f"{word!r} has illegal letter {c!r}")

    # There should be no duplicates
    solutions_set = set(solutions)
    if len(solutions) != len(solutions_set):
        raise ValueError("Solutions contains duplicate words")

    if word_list != ALL_WORDS_TOKEN:
        word_list_set = set(word_list)
        if len(word_list) != len(word_list_set):
            raise ValueError("Word list contains duplicate words")

        if not word_list_set.issuperset(solutions_set):
            raise ValueError("Not all solutions are in word list")

NYTIMES_WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
NYTIMES_WORDLE_JS_CRIB = 'src="https://www.nytimes.com/games-assets/v2/wordle.'

# Known values of wordlists to find them in html / javascript
# NYTIMES_SOLUTIONS_CRIB = '["cigar","rebut","sissy",' # September, 2022
NYTIMES_SOLUTIONS_CRIB = '"cigar","rebut","sissy",' # February, 2023, Solutions are present, but not the start of the array

# NYTIMES_WORD_LIST_CRIB = '["aahed","aalii","aargh",' # June, 2022
NYTIMES_WORD_LIST_CRIB = '["aahed","aalii","aapas",' # September, 2022

def scrap_nytimes():
    # Grab wordle homepage and extract link to javascript
    wordle_page = requests.get(NYTIMES_WORDLE_URL).text

    # Go to crib
    js_crib_index = wordle_page.index(NYTIMES_WORDLE_JS_CRIB)
    # Jump to start of url
    js_url_start = wordle_page.index('"', js_crib_index) + 1
    # Get url end
    js_url_stop = wordle_page.index('"', js_url_start)

    # Extract javascript file
    js_url = wordle_page[js_url_start:js_url_stop]
    assert js_url.endswith(".js"), "failed to extract NYT javascript URL"

    # print("NYT Wordle Javascript URL:", js_url)

    # Grab wordle javascript
    wordle_js = requests.get(js_url).text

    # Go to crib
    solutions_start = wordle_js.index(NYTIMES_SOLUTIONS_CRIB)
    solutions_stop = wordle_js.index("]", solutions_start) + 1

    solutions_raw = wordle_js[solutions_start:solutions_stop]

    # If list does not begin with a bracket, add it
    if solutions_raw[0] != "[":
        solutions_raw = "[" + solutions_raw

    solutions = json.loads(solutions_raw)

    # Get word list
    word_list_start = wordle_js.index(NYTIMES_WORD_LIST_CRIB)
    word_list_stop = wordle_js.index("]", word_list_start) + 1

    word_list_raw = wordle_js[word_list_start:word_list_stop]
    word_list = json.loads(word_list_raw)

    # # NYT word list does not include any of the solutions
    # word_list = word_list + solutions
    # Feb 2023, the word list now contains solutions, just not sorted
    return solutions, word_list

WORDLEGAME_WORD_LIST_URL = "https://wordlegame.org/files/wordle/en/dictionary.json" # September 2022, v39.67
WORDLEGAME_SOLUTIONS_URL = "https://wordlegame.org/files/wordle/en/targets.json" # September 2022, v39.67
# WORDLEGAME_SOLUTIONS_CRIB = '"cigar","rebut","sissy",' # February, 2023, Solutions are present, but not the start of the array

def scrap_wordlegame():
    # wordlegame.org separates solutions and word lists into json, so they are
    # much easier to parse

    # wordlegame.org's solutions and word lists contain values for other than
    # 5 letters. This is because wordlegame.org supports variants for other
    # word sizes. This currently only supports 5 letters, so remove the other words

    # Despite marked with utf-8 encoding, wordlegame.org seems
    # to *sometimes* actually encoded utf-8-sig
    r = requests.get(WORDLEGAME_SOLUTIONS_URL)
    r.encoding = r.apparent_encoding
    solutions = r.json()
    solutions = [word for word in solutions if len(word) == 5]

    # Despite marked with utf-8 encoding, wordlegame.org seems
    # to *sometimes* actually encoded utf-8-sig
    r = requests.get(WORDLEGAME_WORD_LIST_URL)
    r.encoding = r.apparent_encoding
    word_list = r.json()
    word_list = [word for word in word_list if len(word) == 5]

    # Known duplicates that need to be removed
    solutions = list(set(solutions))
    word_list = list(set(word_list))
    return solutions, word_list

def scrap_wordplay():
    # Wordplay does not actually expose the word list, or solutions
    # March 2023, as both Wordplay and NYT are the only known Wordles
    # that accept "seria" as a word, it is assumed wordplay shares
    # word list and solutions with NYT
    return scrap_nytimes()

WORDLEWEBSITE_DAILY_URL = "https://wordlewebsite.com/game/daily-wordle/rs/js/d_wordle.js"

# Known values of wordlists to find them in html / javascript
WORDLEWEBSITE_DAILY_SOLUTIONS_CRIB = '["cigar", "rebut", "sissy",'
WORDLEWEBSITE_DAILY_WORD_LIST_CRIB = '["aahed", "aalii", "aargh",'

def scrap_wordlewebsite_daily():
    # Grab wordle javascript
    wordle_js = requests.get(WORDLEWEBSITE_DAILY_URL).text

    # Remove lines with javascript comments
    # Source contains a commented out list of original wordle list
    wordle_js = "\n".join([line for line in wordle_js.split("\n")
        if "//" not in line and "/*" not in line and "*/" not in line])

    # Go to crib
    solutions_start = wordle_js.index(WORDLEWEBSITE_DAILY_SOLUTIONS_CRIB)
    solutions_stop = wordle_js.index("]", solutions_start) + 1

    solutions_raw = wordle_js[solutions_start:solutions_stop]

    # If list does not begin with a bracket, add it
    if solutions_raw[0] != "[":
        solutions_raw = "[" + solutions_raw

    solutions = json.loads(solutions_raw)

    # Get word list
    word_list_start = wordle_js.index(WORDLEWEBSITE_DAILY_WORD_LIST_CRIB)
    word_list_stop = wordle_js.index("]", word_list_start) + 1

    word_list_raw = wordle_js[word_list_start:word_list_stop]
    word_list = json.loads(word_list_raw)

    # word list does not include any of the solutions
    word_list = word_list + solutions
    return solutions, word_list

# Because Wordle Website seems to use a NYT codebase for the daily, and Wordlegame.org for the "unlimited"
WORDLEWEBSITE_UNLIMITED_WORD_LIST_URL = "https://wordlewebsite.com/game/hurdleunlimited/files/wordle/en/dictionary.json" # March 2023
WORDLEWEBSITE_UNLIMITED_SOLUTIONS_URL = "https://wordlewebsite.com/game/hurdleunlimited/files/wordle/en/targets.json" # March 2023
# WORDLEWEBSITE_UNLIMITED_SOLUTIONS_CRIB = '"aardvark", "abacus", "abbey"' # March 2023

def scrap_wordlewebsite_unlimited():
    # wordlegame.org separates solutions and word lists into json, so they are
    # much easier to parse

    # wordlegame.org's solutions and word lists contain values for other than
    # 5 letters. This is because wordlegame.org supports variants for other
    # word sizes. This currently only supports 5 letters, so remove the other words

    # Despite marked with utf-8 encoding, wordlegame.org seems
    # to *sometimes* actually encoded utf-8-sig
    r = requests.get(WORDLEWEBSITE_UNLIMITED_SOLUTIONS_URL)
    r.encoding = r.apparent_encoding
    solutions = r.json()
    solutions = [word for word in solutions if len(word) == 5]

    # Despite marked with utf-8 encoding, wordlegame.org seems
    # to *sometimes* actually encoded utf-8-sig
    r = requests.get(WORDLEWEBSITE_UNLIMITED_WORD_LIST_URL)
    r.encoding = r.apparent_encoding
    word_list = r.json()
    word_list = [word for word in word_list if len(word) == 5]

    # Known duplicates that need to be removed
    solutions = list(set(solutions))
    word_list = list(set(word_list))
    return solutions, word_list

FLAPPY_BIRDLE_URL = "https://flappybirdle.com"
FLAPPY_BIRDLE_JS_CRIB = 'src="/static/js/main.'

# Known values of wordlists to find them in html / javascript
FLAPPY_BIRDLE_SOLUTIONS_CRIB = '["cigar","rebut","sissy",'

def scrap_flappy_birdle():
    # Grab wordle homepage and extract link to javascript
    wordle_page = requests.get(FLAPPY_BIRDLE_URL).text

    # Go to crib
    js_crib_index = wordle_page.index(FLAPPY_BIRDLE_JS_CRIB)
    # Jump to start of url
    js_url_start = wordle_page.index('"', js_crib_index) + 1
    # Get url end
    js_url_stop = wordle_page.index('"', js_url_start)

    # Extract javascript file
    js_url = wordle_page[js_url_start:js_url_stop]
    assert js_url.endswith(".js"), "failed to extract Birdle javascript URL"

    js_url = urllib.parse.urljoin(FLAPPY_BIRDLE_URL, js_url)
    # print("Birdle Javascript URL:", js_url)

    # Grab wordle javascript
    wordle_js = requests.get(js_url).text

    # Go to crib
    solutions_start = wordle_js.index(FLAPPY_BIRDLE_SOLUTIONS_CRIB)
    solutions_stop = wordle_js.index("]", solutions_start) + 1

    solutions_raw = wordle_js[solutions_start:solutions_stop]
    solutions = json.loads(solutions_raw)

    # # Birdle word list is all possible words
    # Use magic token to indicate all words
    return solutions, ALL_WORDS_TOKEN
