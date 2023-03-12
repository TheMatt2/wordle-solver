from heapq import nsmallest

import wordle_solver
import wordle_contexts
from wordle_contexts import ALL_WORDS_TOKEN, WORD_LENGTH

# TODOs
# - Implement non-heuristic solver
#   - Support hard mode
#   - Prove the heuristic solver is optimal
#   - Min-max both turns to completion, but also use
#     average for tie breaking
#   - Rearrange solver hard mode for "all words" is less awkward
#   - Explore a linear search, like what would be needed for "all words"
#     may have a performance advantage
#
# - Support multiple word lengths
#   - Add additional contexts
#   - Cleanup frontend to support more contexts more
#     elegantly
#
# - Add further cacheing of more than the first word.
#   Don't cache everything, but cache all operations that take
#   more than a set time limit.

def choose_context():
    print("Please select a Wordle version to use:")
    contexts = wordle_contexts.get_contexts()
    for i in range(len(contexts)):
        print(f"{i+1}) {wordle_contexts.get_common_name(contexts[i])}")

    # Have user choose wordle version
    while True:
        choice = input("Wordle version: ").strip()

        if not choice.isdigit():
            print(f"Invalid wordle version choice {choice!r}")
            continue

        choice = int(choice)
        if choice > len(contexts):
            print(f"Invalid wordle version choice {choice!r}")
            continue

        return contexts[choice - 1]

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

def is_result(result):
    # Check if this is a valid result
    # 5 letters, bgy
    if len(result) != WORD_LENGTH:
        return False

    if not {"b", "g", "y"}.issuperset(result):
        return False

    return True

def ask_word(word_list):
    while True:
        word = input("Word: ").strip()

        if len(word) != WORD_LENGTH:
            print(f"{word!r} is not {WORD_LENGTH} letters. Please enter word again.")

        elif word_list != ALL_WORDS_TOKEN and word not in word_list:
            if input(
                f"{word!r} is not in the word list. Use this word anyway? (y/n): "
                ).strip() == "y":
                break
        else:
            # Otherwise, continue normally
            break

    return word

def ask_result(word):
    while True:
        result = input("Result: ").strip()

        # Make sure result format is right
        if not is_result(result):
            print(f"{result!r} is not a valid result. Please enter result again.")

        # Make sure result is possible
        elif not wordle_solver.result_possible(word, result):
            print(f"{result!r} is not possible for {word!r}. Please enter result again.")
            continue

        else:
            # Otherwise, continue normally
            break

    return result

def main():
    # Select Word List
    context = choose_context()
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

    solution_group = wordle_solver.SolutionGroup(solutions)

    # Hard mode doesn't work yet, disable for now
    ## hard_mode = input("Hard Mode?: ").strip() == "y"
    hard_mode = False

    if hard_mode:
        guess_group = solution_group
    elif word_list == ALL_WORDS_TOKEN:
        guess_group = wordle_solver.AllWordsGuessGroup()
    else:
        guess_group = wordle_solver.GuessGroup(word_list)

    # "guesses" is the initial guess for this Wordle game
    # without knowing any information specific to this game
    guesses = wordle_contexts.load_guesses(context, naive)

    if not guesses:
        # Generate initial guesses
        rank, guesses, foils = wordle_solver.best_guesses(guess_group, solution_group)
        wordle_contexts.save_guesses(context, naive, guesses)
    else:
        # Calculate rank and foil for saved values
        foils = []
        for guess in guesses:
            rank, foil = solution_group.guess_rank(guess)
            foils.append(foil)

    print_first_guesses(guesses, foils)
    guess, foil = min(zip(guesses, foils))
    print(f"Best starting word: {guess}")
    print("Words Remaining:", len(solution_group))
    print(f"rank: {rank:.4f} worst case: {foil}")

    while True:
        word = ask_word(word_list)
        result = ask_result(word)

        if result == "ggggg":
            print("Success!")
            break

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
            del guess_b, foil_b
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
            assert len(guesses) == len(foils)
            print_first_guesses(guesses, foils)
            guess, foil = min(zip(guesses, foils))

        # Otherwise, solutions did not change, so no need to update guesses
        # Guesses will be filtered next turn if solutions are removed
        # Print best guess, or the prior guess, if word did not restrict solutions
        print("Best Next Guess:", guess)
        print(f"rank: {rank:.4f} worst case: {foil}")

if __name__ == "__main__":
    main()
