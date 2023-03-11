"""
For a given solution set, benchmark all solutions and see
how many turns on average are taken to solve.
"""
import random

import wordle_main
import wordle_test
import wordle_contexts

from wordle_utils import progress_bar
from wordle_contexts import ALL_WORDS_TOKEN

def main():
    context = wordle_main.choose_context()
    solutions, word_list = wordle_contexts.load_solutions_word_list(context)

    if word_list != ALL_WORDS_TOKEN:
        print(f"Loaded {len(word_list)} words.")
    print(f"Loaded {len(solutions)} possible solutions.")

    # There is no naive mode, if word list is all words
    if word_list != ALL_WORDS_TOKEN:
        naive = input("Naive Mode?: ").strip() == "y"
    else:
        naive = False

    if naive:
        solutions = word_list

    random.shuffle(solutions)

    with open("word_results.txt", "w") as f:
        turns_count = 0
        turns_total = 0
        for solution in progress_bar(solutions):
            turns = wordle_test.test_wordle(context, naive, solution, progress = False)
            turns_total += turns
            turns_count += 1

            print(f"{solution} solved in {turns} Turns average: {turns_total / turns_count:.2f}",
                  file = f, flush = True)

    print(f"Solved in an average of {turns_total / turns_count:.2f} turns.")

if __name__ == "__main__":
    main()
