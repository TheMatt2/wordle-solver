"""
Force generate cache for all game contexts
"""
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
            cache_count = 0
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
                    # Check if value is already cached
                    r, g, f = context.load_guesses()
                    if r is not None:
                        # Show message
                        msg = "Cached"
                    else:
                        new_guess_group = guess_group.copy()
                        r, g, f = wordle_solver.best_guesses(new_guess_group, new_solution_group, progress = None, mp = mp)
                        msg = "Added"

                    cache_count += 1

                context.reset()
                print(f"Cache for {guess!r} ({result}): {msg}")


            # Verify the number of results in the cache
            real_cache_count = len(context._cache_data[guess]["next_turn"])
            if real_cache_count != cache_count:
                print(f"Cache for {guess!r}: {real_cache_count} results in cache, but {cache_count} results were calculated")
                raise RuntimeError(f"Incoherent cache!!! for {guess!r}")
            else:
                print(f"Cache for {guess!r}: {cache_count} results")

"""
# Attempt at multiprocessing
# Abandoned, because it seemed it was possible to corrupt the cache (lock timeout?), and
# I am not convinced it was faster.
import os
import concurrent.futures

def main_mp(mp = True):
    # Go through all game contexts
    if mp is True:
        mp = os.cpu_count()

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
                for result in solution_group.results:
                    # Find result for guess
                    context.next_turn(guess, result)
                    new_solution_group = solution_group.copy()
                    new_solution_group.filter_solutions(guess, result)

                    # Check if value is cached
                    r, g, f = context.load_guesses()
                    cached = r is not None

                    if len(new_solution_group) <= 2:
                        # Result too simple to cache
                        if len(new_solution_group) == 0:
                            msg = "No solutions"
                        elif len(new_solution_group) == 1:
                            msg = "Only one solution"
                        else:
                            msg = "Only two solutions"

                        # Value should not be cached
                        if cached:
                            print(f"Cache for {guess!r} ({result}): Incoherent cache!!! Should be no cache ({msg})")
                            raise RuntimeError(f"Incoherent cache!!! for {guess!r} ({result})")
                        else:
                            print(f"Cache for {guess!r} ({result}): No cache ({msg})")

                        context.reset()
                        continue

                    # Check if value is already cached
                    if cached:
                        # Show message
                        print(f"Cache for {guess!r} ({result}): Cached")
                    else:
                        # Calculate, but don't wait for result
                        future = executor.submit(wordle_solver.best_guesses,
                            guess_group.copy(), new_solution_group, progress = False, mp = False)
                        fs.append(future)
                        rs.append(result)

                        if len(fs) >= mp * 2:
                            # Wait for some to complete
                            concurrent.futures.wait(fs, return_when = concurrent.futures.FIRST_COMPLETED)

                            # Get results of completed once
                            for i in range(len(fs)):
                                future = fs[i]
                                result = rs[i]

                                if future.done():
                                    # Get result (disreguard actual result; already saved)
                                    r, g, f = future.result()

                                    fs[i] = None
                                    rs[i] = None

                                    # Show message
                                    print(f"Cache for {guess!r} ({result}): Added")

                            # Remove processed futures
                            fs = [f for f in fs if f is not None]
                            rs = [r for r in rs if r is not None]

                    context.reset()

                # Wait for all to complete
                # Get results of completed once
                for i in range(len(fs)):
                    future = fs[i]
                    result = rs[i]

                    # Get result (disreguard actual result; already saved)
                    r, g, f = future.result()

                    # Show message
                    print(f"Cache for {guess!r} ({result}): Added")
"""

if __name__ == "__main__":
    main()
    # main_mp()
