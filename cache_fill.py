"""
Force generate cache for all game contexts
"""
import time
import wordle_solver
import wordle_contexts

def main():
    # Go through all game contexts
    mp = True
    for context in wordle_contexts.get_all_contexts():
        print(f"Building cache for {'naive' if context.naive else 'smart'} {context.name} Length {context.word_length}")

        # Setup solver
        guess_group = context.get_guess_group()
        solution_group = context.get_solution_group()

        # Get initial guesses
        rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group, mp = mp)
        for guess in guesses:
            unsaved_results = 0
            max_unsaved_results = 10
            cache_results = set()
            try:
                for result, new_solution_group in solution_group.partition(guess, sort = True):
                    # Find result for guess
                    context.next_turn(guess, result)

                    if len(new_solution_group) <= 2:
                        # Result too simple to cache
                        assert len(new_solution_group) > 0
                        if len(new_solution_group) == 1:
                            msg = "No cache (Only one solution)"
                        else:
                            msg = "No cache (Only two solutions)"

                    else:
                        cache_results.add(result)

                        # Check if value is already cached
                        r, g, f = context.load_guesses()
                        if r is not None:
                            # Show message
                            msg = "Cached"
                        else:
                            # Do not use the cache, override and save manually
                            r, g, f = wordle_solver.best_guesses(guess_group.copy(),
                                new_solution_group, progress = None, mp = mp, cache = False)

                            msg = "Added"
                            unsaved_results += 1

                            # Save without flushing to disk
                            context._save_guesses_internal(r, g, f)
                            if unsaved_results >= max_unsaved_results:
                                # Save to disk
                                context._save_guess_data()
                                unsaved_results = 0

                    context.reset()
                    print(f"Cache for {guess!r} ({result}): {msg}")
            finally:
                # Make sure all words are saved
                if unsaved_results:
                    context._save_guess_data()

            # Verify the number of results in the cache
            try:
                real_cache_results = set(context._cache_data[guess]["next_turn"])
            except KeyError:
                # No results in cache, despite filling it
                # Means the guess must be very good
                continue

            if cache_results != real_cache_results:
                print(
                    f"Cache for {guess!r}: {len(real_cache_results)} results "
                    f"in cache, but {len(cache_results)} results were calculated")

                for result in sorted(cache_results.difference(real_cache_results),
                        key = wordle_solver._result_key):
                    print(f"Cache for {guess!r}: result {result} was calculated but not in cache")

                for result in sorted(real_cache_results.difference(cache_results),
                        key = wordle_solver._result_key):
                    # Check if the result is possible
                    if wordle_solver.is_result_possible(guess, result, context):
                        print(f"Cache for {guess!r}: result {result} is in "
                            f"cache but was not calculated (but possible)")
                    else:
                        print(f"Cache for {guess!r}: result {result} is in cache but not possible")
                        # del context._cache_data[guess]["next_turn"][result]

                # context._save_guess_data()
                exit(1)
            else:
                print(f"Cache for {guess!r}: {len(cache_results)} results")

import os
import concurrent.futures

def main_mp(mp = True):
    # Go through all game contexts
    if mp is True:
        mp = os.cpu_count()

    max_unsaved_jobs = mp * 8
    for context in wordle_contexts.get_all_contexts():
        print(f"Building cache for {'naive' if context.naive else 'smart'} {context.name} Length {context.word_length}")

        # Setup solver
        guess_group = context.get_guess_group()
        solution_group = context.get_solution_group()

        # Get initial guesses
        rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group, mp = mp)
        for guess in guesses:
            with concurrent.futures.ProcessPoolExecutor(mp) as executor:
                fs = []
                rs = []
                cache_results = set()
                for result, new_solution_group in solution_group.partition(guess, sort = True):
                    # Find result for guess
                    context.next_turn(guess, result)

                    if len(new_solution_group) <= 2:
                        # Result too simple to cache
                        assert len(new_solution_group) > 0
                        if len(new_solution_group) == 1:
                            msg = "Only one solution"
                        else:
                            msg = "Only two solutions"

                        # Value should not be cached
                        print(f"Cache for {guess!r} ({result}): No cache ({msg})")
                        context.reset()
                        continue

                    cache_results.add(result)
                    # Check if value is already cached
                    r, g, f = context.load_guesses()
                    context.reset()
                    if r is not None:
                        # Show message
                        print(f"Cache for {guess!r} ({result}): Cached")
                    else:
                        # Calculate, but don't wait for result
                        future = executor.submit(wordle_solver.best_guesses,
                            guess_group.copy(), new_solution_group, progress = False, mp = False, cache = False)
                        fs.append(future)
                        rs.append(result)

                        if len(fs) >= max_unsaved_jobs:
                            # Get results once completed
                            for i in range(len(fs)):
                                future = fs[i]
                                result = rs[i]

                                # Get result
                                r, g, f = future.result()
                                context.next_turn(guess, result)
                                context._save_guesses_internal(r, g, f)
                                context.reset()

                                # Show message
                                print(f"Cache for {guess!r} ({result}): Added")

                            # Force save
                            context._save_guess_data()
                            # Reset futures
                            fs = []
                            rs = []

                # Wait for all to complete
                # Get results of completed once
                for i in range(len(fs)):
                    future = fs[i]
                    result = rs[i]

                    # Get result
                    r, g, f = future.result()
                    context.next_turn(guess, result)
                    context._save_guesses_internal(r, g, f)
                    context.reset()

                    # Show message
                    print(f"Cache for {guess!r} ({result}): Added")

                # Force save
                context._save_guess_data()

            # Verify the number of results in the cache
            try:
                real_cache_results = set(context._cache_data[guess]["next_turn"])
            except KeyError:
                # No results in cache, despite filling it
                # Means the guess must be very good
                continue

            if cache_results != real_cache_results:
                print(
                    f"Cache for {guess!r}: {len(real_cache_results)} results "
                    f"in cache, but {len(cache_results)} results were calculated")

                for result in sorted(cache_results.difference(real_cache_results),
                        key = wordle_solver._result_key):
                    print(f"Cache for {guess!r}: result {result} was calculated but not in cache")

                for result in sorted(real_cache_results.difference(cache_results),
                        key = wordle_solver._result_key):
                    # Check if the result is possible
                    if wordle_solver.is_result_possible(guess, result, context):
                        print(
                            f"Cache for {guess!r}: result {result} is "
                            "in cache but was not calculated (but possible)")
                    else:
                        print(
                            f"Cache for {guess!r}: result {result} is "
                            "in cache but not possible")
                        # del context._cache_data[guess]["next_turn"][result]

                # context._save_guess_data()
                exit(1)

if __name__ == "__main__":
    start = time.time()
    try:
        main()
        # main_mp()
    finally:
        stop = time.time()
        print(f"Built word cache in {stop - start:.4f} secs")
