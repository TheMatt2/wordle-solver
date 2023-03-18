"""
Force generate cache for all game contexts
"""
import wordle_solver
import wordle_contexts

def main():
    # Go through all game contexts
    for context in wordle_contexts.get_all_contexts():
        print(f"Building cache for {'naive' if context.naive else 'smart'} {context.name} Length {context.word_length}")

        # Setup solver
        guess_group = context.get_guess_group()
        solution_group = context.get_solution_group()

        # Get initial guesses
        rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group)
        for guess in guesses:
            for result in solution_group.results:
                print(f"Calculating cache for {guess!r} ({result}): ", end = "")
                # Find result for guess
                context.next_turn(guess, result)
                new_solution_group = solution_group.copy()
                new_solution_group.filter_solutions(guess, result)

                if len(new_solution_group) <= 2:
                    # Result too simple to cache
                    if len(new_solution_group) == 0:
                        print("No solutions")
                    elif len(new_solution_group) == 1:
                        print("One solution")
                    else:
                        print("Two solutions")

                    context.reset()
                    continue

                new_guess_group = guess_group.copy()
                wordle_solver.best_guesses(new_guess_group, new_solution_group, progress = None)
                print("Cached")
                context.reset()

if __name__ == "__main__":
    main()
