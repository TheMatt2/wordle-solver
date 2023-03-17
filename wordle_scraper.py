"""
wordle_scraper.py

Manage word lists and solution sets for Wordle games.

Two Wordle Games are currently supported:
 - https://wordlegame.org
 - https://www.nytimes.com/games/wordle
"""
import json
import hjson
import requests
import urllib.parse

from wordle_contexts import ALL_WORDS_TOKEN

NYTIMES_WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
NYTIMES_WORDLE_JS_CRIB = 'src="https://www.nytimes.com/games-assets/v2/wordle.'

# Known values of wordlists to find them in html / javascript
# NYTIMES_WORD_LIST_CRIB = '["aahed","aalii","aargh",' # June, 2022
NYTIMES_WORD_LIST_CRIB = '["aahed","aalii","aapas",' # September, 2022

# NYTIMES_SOLUTIONS_CRIB = '["cigar","rebut","sissy",' # September, 2022
NYTIMES_SOLUTIONS_CRIB = '"cigar","rebut","sissy",' # February, 2023, Solutions are present, but not the start of the array

def get_quoted_crib(content, crib, start_quote = '"', stop_quote = '"', keep_quotes = False):
    """Extract a quoted segment with the given crib of content"""
    # Go to crib
    index = content.index(crib)
    # Find start
    start = content.index(start_quote, index)
    # Find stop
    stop = content.index(stop_quote, start + len(start_quote))
    # Return segment, not including quotes

    if keep_quotes:
        return content[start: stop + len(stop_quote)]
    else:
        return content[start + len(start_quote): stop]

def get_bracketed_crib(content, crib, start_quote = '[', stop_quote = ']', keep_quotes = True):
    """Extract a bracketed segment with the given crib of content"""
    return get_quoted_crib(content, crib, start_quote, stop_quote, keep_quotes)

def scrap_nytimes():
    # Grab wordle homepage and extract link to javascript
    wordle_page = requests.get(NYTIMES_WORDLE_URL).text

    # Extract javascript file
    js_url = get_quoted_crib(wordle_page, NYTIMES_WORDLE_JS_CRIB)
    assert js_url.endswith(".js"), "failed to extract NYT javascript URL"

    # Grab wordle javascript
    wordle_js = requests.get(js_url).text

    # Get word list
    word_list_raw = get_bracketed_crib(wordle_js, NYTIMES_WORD_LIST_CRIB)
    word_list = json.loads(word_list_raw)

    # Go to crib
    solutions_raw = get_bracketed_crib(wordle_js, NYTIMES_SOLUTIONS_CRIB, "", "]")

    # List does not begin with a bracket, add it
    solutions_raw = "[" + solutions_raw
    solutions = json.loads(solutions_raw)

    # # NYT word list does not include any of the solutions
    # word_list = word_list + solutions
    # Feb 2023, the word list now contains solutions, just not sorted
    return word_list, solutions

WORDLEGAME_WORD_LIST_URL = "https://wordlegame.org/files/wordle/en/dictionary.json" # September 2022, v39.67
WORDLEGAME_SOLUTIONS_URL = "https://wordlegame.org/files/wordle/en/targets.json" # September 2022, v39.67
# WORDLEGAME_SOLUTIONS_CRIB = '"cigar","rebut","sissy",' # February, 2023, Solutions are present, but not the start of the array

# Diacritics from https://wordlegame.org/files/wordle/en/config.json?v42.11
WORDLE_GAME_DIACRITICS = {}

# Format to avoid unicode in source
for letter, diacritics in {
    'a': '\xe0\xe1\xe2\xe3\xe4\xe5',
    'c': '\xe7',
    'e': '\xe8\xe9\xea\xeb',
    'i': '\xec\xed\xee\xef',
    'n': '\xf1',
    'o': '\xf2\xf3\xf4\xf5\xf6',
    'u': '\xf9\xfa\xfb\xfc',
    'y': '\xfd\xff'}.items():
    for diacritic in diacritics:
        WORDLE_GAME_DIACRITICS[diacritic] = letter

del letter, diacritic, diacritics

def wordle_game_internal(url):
    # Despite marked with utf-8 encoding, wordlegame.org seems
    # to *sometimes* actually encoded utf-8-sig
    r = requests.get(url)
    r.encoding = r.apparent_encoding
    raw_word_list = r.json()

    # Remove diacritics
    word_list = []
    for word in raw_word_list:
        word = "".join([WORDLE_GAME_DIACRITICS.get(c, c) for c in word])
        word_list.append(word)

    return word_list

def scrap_wordlegame():
    # wordlegame.org separates solutions and word lists into json, so they are
    # much easier to parse
    word_list = wordle_game_internal(WORDLEGAME_WORD_LIST_URL)
    solutions = wordle_game_internal(WORDLEGAME_SOLUTIONS_URL)

    # Known duplicates that need to be removed
    word_list = list(set(word_list))
    solutions = list(set(solutions))
    return word_list, solutions

def scrap_wordplay():
    # Wordplay does not actually expose the word list, or solutions
    # March 2023, as both Wordplay and NYT are the only known Wordles
    # that accept "seria" as a word, it is assumed wordplay shares
    # word list and solutions with NYT
    # Update: "olate" is not considered a valid word.
    #    Which is consistant with the old NYT word list.
    #    There are no known word list that include "seria" but exclude "olate"
    #    Yet "tangy" is a solution.
    #    This seems to indicate the exact word list is different than any known.
    return scrap_wordlewebsite_daily()

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

    # Get word list
    word_list_raw = get_bracketed_crib(wordle_js, WORDLEWEBSITE_DAILY_WORD_LIST_CRIB, "[", "]")
    word_list = json.loads(word_list_raw)

    # Go to crib
    solutions_raw = get_bracketed_crib(wordle_js, WORDLEWEBSITE_DAILY_SOLUTIONS_CRIB, "[", "]")
    solutions = json.loads(solutions_raw)

    # word list does not include any of the solutions
    word_list = word_list + solutions
    return word_list, solutions

# Because Wordle Website seems to use a NYT codebase for the daily, and Wordlegame.org for the "unlimited"
WORDLEWEBSITE_UNLIMITED_WORD_LIST_URL = "https://wordlewebsite.com/game/hurdleunlimited/files/wordle/en/dictionary.json" # March 2023
WORDLEWEBSITE_UNLIMITED_SOLUTIONS_URL = "https://wordlewebsite.com/game/hurdleunlimited/files/wordle/en/targets.json" # March 2023
# WORDLEWEBSITE_UNLIMITED_SOLUTIONS_CRIB = '"aardvark", "abacus", "abbey"' # March 2023

def scrap_wordlewebsite_unlimited():
    # wordlegame.org separates solutions and word lists into json, so they are
    # much easier to parse
    word_list = wordle_game_internal(WORDLEWEBSITE_UNLIMITED_WORD_LIST_URL)
    solutions = wordle_game_internal(WORDLEWEBSITE_UNLIMITED_SOLUTIONS_URL)
    return word_list, solutions

ABSURDLE_URL = "https://qntm.org/files/absurdle/absurdle.html"
ABSURDLE_JS_CRIB = 'src="main.'

# Known values of wordlists to find them in html / javascript
ABSURDLE_SOLUTIONS_CRIB = 'N=R({CI:"GARVI'
ABSURDLE_WORD_LIST_CRIB = 'I=R({AA:"HEDLI'

def scrap_absurdle():
    wordle_page = requests.get(ABSURDLE_URL).text

    # Extract javascript file
    js_url = get_quoted_crib(wordle_page, ABSURDLE_JS_CRIB)
    assert js_url.endswith(".js"), "failed to extract Absurdle javascript URL"

    js_url = urllib.parse.urljoin(ABSURDLE_URL, js_url)

    # Grab wordle javascript
    wordle_js = requests.get(js_url).text

    # Extract word list as json object
    word_list_raw = get_bracketed_crib(wordle_js, ABSURDLE_WORD_LIST_CRIB, "{", "}")
    word_list_json = hjson.loads(word_list_raw)

    word_list = []
    for prefix, remaining in word_list_json.items():
        for i in range(0, len(remaining), 5 - len(prefix)):
            suffix = remaining[i:i + 5 - len(prefix)]
            word_list.append((prefix + suffix).lower())

    # Get solutions
    # Extract word list as json object
    solutions_raw = get_bracketed_crib(wordle_js, ABSURDLE_SOLUTIONS_CRIB, "{", "}")
    solutions_json = hjson.loads(solutions_raw)

    solutions = []
    for prefix, remaining in solutions_json.items():
        for i in range(0, len(remaining), 5 - len(prefix)):
            suffix = remaining[i:i + 5 - len(prefix)]
            solutions.append((prefix + suffix).lower())

    # Add solutions to word list
    word_list = word_list + solutions

    # Remove duplicates
    word_list = list(set(word_list))
    solutions = list(set(solutions))

    return word_list, solutions

FLAPPY_BIRDLE_URL = "https://flappybirdle.com"
FLAPPY_BIRDLE_JS_CRIB = 'src="/static/js/main.'

# Known values of wordlists to find them in html / javascript
FLAPPY_BIRDLE_SOLUTIONS_CRIB = '["cigar","rebut","sissy",'

def scrap_flappy_birdle():
    # Grab wordle homepage and extract link to javascript
    wordle_page = requests.get(FLAPPY_BIRDLE_URL).text

    # Extract javascript file
    js_url = get_quoted_crib(wordle_page, FLAPPY_BIRDLE_JS_CRIB)
    assert js_url.endswith(".js"), "failed to extract Birdle javascript URL"

    js_url = urllib.parse.urljoin(FLAPPY_BIRDLE_URL, js_url)

    # Grab wordle javascript
    wordle_js = requests.get(js_url).text

    solutions_raw = get_bracketed_crib(wordle_js, FLAPPY_BIRDLE_SOLUTIONS_CRIB)
    solutions = json.loads(solutions_raw)

    # Birdle word list is all possible words
    # Use magic token to indicate all words
    return [ALL_WORDS_TOKEN], solutions
