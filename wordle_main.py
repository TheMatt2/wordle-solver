import wordle_solver
import wordle_contexts

# Top guesses
# aesir
# arise
# raise
# serai

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
    if len(result) != 5:
        return False

    if not {"b", "g", "y"}.issuperset(result):
        return False

    return True

def main():
    # Select Word List
    context = choose_context()
    solutions, word_list = wordle_contexts.load_solutions_word_list(context)

    print(f"Loaded {len(word_list)} words.")
    print(f"Loaded {len(solutions)} possible solutions.")

    naive = input(
        "Should the computer assume any word can be a solution?: "
        ).strip() == "y"

    if naive:
        solutions = word_list

    solution_group = wordle_solver.SolutionGroup(solutions)
    hard_mode = input("Hard Mode?: ").strip() == "y"

    if hard_mode:
        guess_group = solution_group
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
