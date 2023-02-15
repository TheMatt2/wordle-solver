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

    # TODO properly bounds check input
    choice = input("Wordle version: ")
    context = contexts[int(choice)-1]
    return context

def print_best_guesses(guesses, count = 10):
    for guess in sorted(guesses):
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
    solutions, word_list = wordle_contexts.get_solutions_word_list(context)

    print(f"Loaded {len(word_list)} words.")
    print(f"Loaded {len(solutions)} possible solutions.")

    naive = input(
        "Should the computer play naively (assume any word can be a solution)?: "
        ).strip() == "y"

    if naive:
        solutions = word_list

    word_stats = wordle_solver.WordStats(solutions)

    if naive:
        guesses = wordle_contexts.get_naive_guesses(context)
    else:
        guesses = wordle_contexts.get_smart_guesses(context)

    if not guesses:
        guesses, _ = wordle_solver.best_guesses(word_list, word_stats)

        if naive:
            wordle_contexts.set_naive_guesses(context, guesses)
        else:
            wordle_contexts.set_smart_guesses(context, guesses)

    print_best_guesses(guesses)
    guesses.sort()
    word = guesses[0]
    print(f"Best starting word: {word}")
    rank, foil = wordle_solver.word_rank(word, word_stats)
    print(f"rank: {rank} worst case: {foil}")
    print("Words Remaining:", len(word_stats))

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
        word_stats.filter(word, result)

        print("Words Remaining:", len(word_stats))

        for i, word in enumerate(word_stats):
            print(word)
            if i == 10:
                break
        print()

        if len(word_stats) == 2:
            # Only two or less words
            # Best solution is to guess one of the words
            words = sorted(word_stats)
            word = words[0]
            print("Best Next Guess:", words[0])
            print("Failing Guess:", words[1])
            continue

        if len(word_stats) == 1:
            # Only one solution
            word = next(iter(word_stats))
            print("Best Next Guess:", word)
            break

        if len(word_stats) == 0:
            # No remaining solutions
            print("There are no possible remaining solutions.")
            break

        guesses, rank = wordle_solver.best_guesses(word_list, word_stats)
        print_best_guesses(guesses)
        guesses.sort()
        word = guesses[0]
        print("Best Next Guess:", word)

if __name__ == "__main__":
    main()
