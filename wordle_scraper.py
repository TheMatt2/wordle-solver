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

letters = "abcdefghijklmnopqrstuvwxyz"

NYTIMES_WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
NYTIMES_WORDLE_JS_CRIB = 'src="https://www.nytimes.com/games-assets/v2/wordle.'

# Known values of wordlists to find them in html / javascript
NYTIMES_SOLUTIONS_CRIB = '["cigar","rebut","sissy",'
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
    solutions = json.loads(solutions_raw)

    # Get word list
    word_list_start = wordle_js.index(NYTIMES_WORD_LIST_CRIB)
    word_list_stop = wordle_js.index("]", word_list_start) + 1

    word_list_raw = wordle_js[word_list_start:word_list_stop]
    word_list = json.loads(word_list_raw)

    # NYT word list does not include any of the solutions
    word_list = word_list + solutions
    return solutions, word_list

WORDLEGAME_WORD_LIST_URL = "https://wordlegame.org/files/wordle/en/dictionary.json" # September 2022, v39.67
WORDLEGAME_SOLUTIONS_URL = "https://wordlegame.org/files/wordle/en/targets.json" # September 2022, v39.67

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

def check_solutions_word_lists(solutions, word_list):
    # Verify solution and word lists make sense
    for word in solutions + word_list:
        if len(word) != 5:
            raise ValueError(
                "Word encountered that is not five letters: {:r}".format(word))

        for c in word:
            if c not in letters:
                raise ValueError(
                    "Word encountered with illegal letter: {:r}".format(word))

    # There should be no duplicates
    solutions_set = set(solutions)
    if len(solutions) != len(solutions_set):
        raise ValueError(
            "Solutions contains duplicate words")

    word_list_set = set(word_list)
    if len(word_list) != len(word_list_set):
        raise ValueError(
            "Word list contains duplicate words")

    if not word_list_set.issuperset(solutions_set):
        raise ValueError(
            "Not all solutions are in word list")

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

    # Birdle word list is all possible words
    word_list = []

    for word in itertools.product(*[letters] * 5):
        word_list.append("".join(word))

    return solutions, word_list
