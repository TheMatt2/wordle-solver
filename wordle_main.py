from heapq import nsmallest

import wordle_solver
import wordle_contexts

# TODOs
# - Implement non-heuristic solver
#   - Support hard mode
#   - Prove the heuristic solver is optimal
#   - Min-max both turns to completion, but also use
#     average for tie breaking
#   - Rearrange solver hard mode for "all words" is less awkward
#   - Explore a linear search, like what would be needed for "all words"
#     may have a performance advantage

def print_first_solutions(solutions, count = 10):
    for solution in nsmallest(count, solutions):
        print(solution)

    if len(solutions) > count:
        print("...")
    print()

def print_first_guesses(guesses, foils, count = 10):
    for guess, foil in nsmallest(count, zip(guesses, foils)):
        print(f"{guess} ({foil})")

    if len(guesses) > count:
        print("...")
    print()

def is_result(result, context):
    # Check if this is a valid result
    # 5 letters, bgy
    if len(result) != context.word_length:
        return False

    if not {"b", "g", "y"}.issuperset(result):
        return False

    return True

def ask_word(context):
    """Ask use for a word to guess."""
    while True:
        word = input("Word: ").strip()

        if len(word) != context.word_length:
            print(f"{word!r} is not {context.word_length} letters. Please enter word again.")

        elif not context.is_valid_word(word):
            if input(
                f"{word!r} is not in the word list. Use this word anyway? (y/n): "
                ).strip() == "y":
                break
        else:
            # Otherwise, continue normally
            break

    return word

def ask_result(word, context):
    while True:
        result = input("Result: ").strip()

        # Make sure result format is right
        if not is_result(result, context):
            print(f"{result!r} is not a valid result. Please enter result again.")

        # Make sure result is possible
        elif not wordle_solver.is_result_possible(word, result, context):
            print(f"{result!r} is not possible for {word!r}. Please enter result again.")
            continue

        else:
            # Otherwise, continue normally
            break

    return result

def main():
    # Select Game Context
    context = wordle_contexts.ask_context()

    # Get word groups
    guess_group = context.get_guess_group()
    solution_group = context.get_solution_group()

    print(f"There are {len(guess_group)} possible guesses.")
    print(f"There are {len(solution_group)} possible solutions.")

    rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group)

    print_first_guesses(guesses, foils)
    guess, foil = min(zip(guesses, foils))
    print(f"Best starting word: {guess}")
    print("Words Remaining:", len(solution_group))
    print(f"Rank: {rank:.4f} Worst Case: {foil}")

    while True:
        word = ask_word(context)
        result = ask_result(word, context)

        if result == "g" * context.word_length:
            print("Success!")
            break

        # Tell context word was guessed for caching to work
        context.next_turn(word, result)

        # Find number of words remaining
        # Track prior count to see if solutions were removed
        solution_count = len(solution_group)
        solution_group.filter_solutions(word, result)

        print("Words Remaining:", len(solution_group))
        print_first_solutions(solution_group)

        if len(solution_group) == 2:
            # Only two or less words
            # Best solution is to guess one of the words
            guess, guess_b = sorted(solution_group)
            _, foil = solution_group.guess_rank(guess)
            _, foil_b = solution_group.guess_rank(guess_b)

            print(f"Best Next Guess: {guess} ({foil})")
            print(f"Failing Guess: {guess_b} ({foil_b})")
            del guess_b, foil_b # avoid namespace pollution
            continue

        if len(solution_group) == 1:
            # Only one solution
            guess = next(iter(solution_group))
            _, foil = solution_group.guess_rank(guess)
            print(f"Best Next Guess: {guess} ({foil})")
            break

        if len(solution_group) == 0:
            # No remaining solutions
            print("There are no possible remaining solutions.")
            break

        if solution_count != len(solution_group):
            # Solutions changed, so update guesses
            rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group)
            print_first_guesses(guesses, foils)
            guess, foil = min(zip(guesses, foils))

        # Otherwise, solutions did not change, so no need to update guesses
        # Guesses will be filtered next turn if solutions are removed
        # Print best guess, or the prior guess, if word did not restrict solutions
        print("Best Next Guess:", guess)
        print(f"rank: {rank:.4f} worst case: {foil}")

if __name__ == "__main__":
    main()
