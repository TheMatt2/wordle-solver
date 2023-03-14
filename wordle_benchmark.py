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

import wordle_test
import wordle_contexts

from wordle_utils import progress_bar

def main():
    context = wordle_contexts.ask_context()

    print(f"Word list has {len(context.word_list)} words.")
    print(f"There are {len(context.solutions)} possible solutions.")

    # Make sure initial guess is generated
    context.get_initial_guesses()
    benchmark(context)

def _wordle_test_mp(solution, context, progress = False, mp = False):
    turns = wordle_test.wordle_test(solution, context, progress = progress, mp = mp)
    return solution, turns

def benchmark(context, mp = True):
    solutions = context.solutions

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
            for fd in [f, None]:
                print(f"Calculating Benchmark using {mp} processes...", file = fd)

            with concurrent.futures.ProcessPoolExecutor(mp) as executor:
                for solution, turns in progress_bar(executor.map(
                        partial(_wordle_test_mp, context = context),
                        solutions), len(solutions)):

                    turn_count += 1
                    turn_total += turns
                    turn_stats[turns] += 1

                    print(f"{solution} solved in {turns} "
                        f"Turns average: {turn_total / turn_count:.2f}",
                        file = f, flush = True)
        else:
            for solution in progress_bar(solutions):
                turns = wordle_test.wordle_test(solution, context, progress = False, mp = False)
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
