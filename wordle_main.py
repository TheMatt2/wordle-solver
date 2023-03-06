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
#
# - Improve progress bar
#   - Update progress so the estimate is the time for the longest running
#     process to finish.
#   - Make sure that a crash in a worker thread doesn't cause the entire program to freeze
#

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

def print_first(guesses, count = 10):
    for guess in guesses:
        print(guess)
        count -= 1
        if not count: break
    print()

def is_result(result):
    # Check if this is a valid result
    # 5 letters, bgy
    if len(result) != WORD_LENGTH:
        return False

    if not {"b", "g", "y"}.issuperset(result):
        return False

    return True

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
    init_guesses = wordle_contexts.load_guesses(context, naive)

    if not init_guesses:
        # Generate initial guesses
        init_guesses, _ = wordle_solver.best_guesses(guess_group, solution_group)
        wordle_contexts.save_guesses(context, naive, init_guesses)

    init_guesses.sort()
    print_first(init_guesses)
    word = init_guesses[0]
    print(f"Best starting word: {word}")
    rank, foil = solution_group.guess_rank(word)
    print(f"rank: {rank} worst case: {foil}")
    print("Words Remaining:", len(solution_group))

    while True:
        while True:
            word = input("Word: ").strip()

            if len(word) == WORD_LENGTH and word_list == ALL_WORDS_TOKEN:
                # Skip word list check
                break

            if word in word_list:
                # Valid, exit
                break

            if input(
                f"{word!r} is not in the word list. Use this word anyway? (y/n): "
                ).strip() == "y":
                break

        while True:
            result = input("Result: ").strip()
            if is_result(result):
                # Valid, exit
                break

            print(f"{result!r} is not a valid result. Please enter result again.")

        if result == "ggggg":
            print("Success!")
            break

        # Find number of words remaining
        solution_group.filter_solutions(word, result)

        print("Words Remaining:", len(solution_group))
        print_first(solution_group)

        if len(solution_group) == 2:
            # Only two or less words
            # Best solution is to guess one of the words
            words = sorted(solution_group)
            word = words[0]
            print("Best Next Guess:", words[0])
            print("Failing Guess:", words[1])
            continue

        if len(solution_group) == 1:
            # Only one solution
            word = next(iter(solution_group))
            print("Best Next Guess:", word)
            break

        if len(solution_group) == 0:
            # No remaining solutions
            print("There are no possible remaining solutions.")
            break

        init_guesses, rank = wordle_solver.best_guesses(guess_group, solution_group)
        init_guesses.sort()
        print_first(init_guesses)
        word = init_guesses[0]
        print("Best Next Guess:", word)

if __name__ == "__main__":
    main()
