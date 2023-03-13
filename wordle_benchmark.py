"""
For a given solution set, benchmark all solutions and see
how many turns on average are taken to solve.
"""
import time
import random
import concurrent.futures
from functools import partial
from collections import Counter
from multiprocessing import cpu_count

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

    benchmark(solutions, context, naive)

def _wordle_test_mp(solution, context, naive, progress = False, mp = False):
    turns = wordle_test.test_wordle(
        context, naive, solution, progress = progress, mp = mp)
    return solution, turns

def benchmark(solutions, context, naive, mp = True):
    random.seed(12345)
    random.shuffle(solutions)

    with open("word_results.txt", "w") as f:
        turn_count = 0
        turn_total = 0
        turn_stats = Counter()

        if mp is True:
            mp = cpu_count()

        start = time.perf_counter()
        if mp:
            # Use multiprocessing to accelerate processing
            with concurrent.futures.ProcessPoolExecutor(mp) as executor:
                for solution, turns in progress_bar(executor.map(
                        partial(_wordle_test_mp, context = context, naive = naive),
                        solutions), len(solutions)):

                    turn_count += 1
                    turn_total += turns
                    turn_stats[turns] += 1

                    print(f"{solution} solved in {turns} "
                        f"Turns average: {turn_total / turn_count:.2f}",
                        file = f, flush = True)
        else:
            for solution in progress_bar(solutions):
                turns = wordle_test.test_wordle(
                    context, naive, solution, progress = False, mp = False)
                turn_count += 1
                turn_total += turns
                turn_stats[turns] += 1

                print(f"{solution} solved in {turns} "
                    f"Turns average: {turn_total / turn_count:.2f}",
                    file = f, flush = True)

        stop = time.perf_counter()

        # Print both to file and stdout
        for fd in [f, None]:
            print(file = fd)
            for i in range(min(turn_stats.keys()), max(turn_stats.keys()) + 1):
                print(f"Solved {turn_stats[i]} words in {i} turns", file = fd)

            print(f"Solved words an average of {turn_total / turn_count:.2f} "
                f"turns in {stop - start:.2f} secs", file = fd)

if __name__ == "__main__":
    main()
