import time

import wordle_solver
import wordle_contexts

# Use coloring if avaliable
try:
    from colorama import init, Back
except ImportError:
    # Don't color as colorama is not installed
    init = lambda: None
    def wordle_coloring(guess, result):
        return f"{guess} ({result})"
else:
    def wordle_coloring(guess, result):
        """Adding black, yellow, green coloring for wordle coloring"""
        coloring = []
        for g, r in zip(guess, result):
            if   r == "g": color = Back.GREEN
            elif r == "y": color = Back.YELLOW
            elif r == "b": color = Back.BLACK
            coloring.append(color + g)

        return "".join(coloring) + Back.RESET + f" ({result})"

word_length = 5
letters = "abcdefghijklmnopqrstuvwxyz"

def wordle_result(guess, solution):
    """Given a guess and solution, generate the coloring wordle would show"""
    # Result calculation is basically check if guess letter matches
    # solution, but there is some complexity to account for duplicate
    # letters.

    # "u" is unassigned temporary value
    result = ["u"] * word_length

    # First Pass, Correct and Absent
    for index in range(word_length):
        if guess[index] == solution[index]:
            # Correct
            result[index] = "g"
        elif guess[index] not in solution:
            # Absent
            result[index] = "b"

    # Second Pass Count Remaining Letters
    # Count letters
    solution_letters = {l: 0 for l in letters}
    for index in range(word_length):
        if result[index] != "g":
            solution_letters[solution[index]] += 1

    # Third Pass
    # Mark Present
    for index in range(word_length):
        if result[index] == "u":
            # Evaluate if Present
            assert guess[index] in solution

            # If letters remaining, mark as present
            # Left to Right
            if solution_letters[guess[index]]:
                solution_letters[guess[index]] -= 1
                result[index] = "y"
            else:
                # None Remaining
                result[index] = "b"

    return "".join(result)

def test_wordle(context, naive, solution = None):
    """Play wordle, and time how long it takes.
       If no solution is provided, a worst case scenario is calculated.
       The worst case solution is known as the "foil"
    """
    solutions, word_list = wordle_contexts.load_solutions_word_list(context)
    if naive:
        solutions = word_list

    word_stats = wordle_solver.WordStats(solutions)

    # "guesses" is the initial guess for this Wordle game
    # without knowing any information specific to this game
    guesses = wordle_contexts.load_guesses(context, naive)

    if not guesses:
        # Generate initial guesses
        print("Generating Initial Guesses. Not included in testing time, but will take a while.")
        guesses, rank = wordle_solver.best_guesses(word_list, word_stats)
        wordle_contexts.save_guesses(context, naive, guesses)

    guesses.sort()
    word = guesses[0]

    start = time.perf_counter()

    while True:
        # If no solution, use foil
        if solution:
            result = wordle_result(word, solution)
        else:
            rank, foil = wordle_solver.word_rank(word, word_stats)
            result = foil

        print(wordle_coloring(word, result))

        if result == "ggggg":
            if not solution:
                solution = word

            print("Success!")
            break

        # Find number of words remaining
        word_stats.filter(word, result)

        if len(word_stats) == 2:
            # Only two or less words
            # Best solution is to guess one of the words
            words = sorted(word_stats)
            word = words[0]
            continue

        if len(word_stats) == 1:
            # Only one solution
            word = next(iter(word_stats))
            continue

        if len(word_stats) == 0:
            # No remaining solutions
            print("There are no possible remaining solutions.")
            break

        guesses, rank = wordle_solver.best_guesses(word_list, word_stats, progress = False)
        guesses.sort()
        word = guesses[0]

    stop = time.perf_counter()

    print(
        f"Test: {wordle_contexts.get_common_name(context)}, Naive: {naive}, "
        f"Solution: {solution}, Duration: {stop - start:.4f} seconds\n")

def main():
    init()

    start = time.perf_counter()
    for solution in [None, "magic", "abort", "krill", "staff"]:
        test_wordle("new_york_times", False, solution)
        test_wordle("wordlegame_org", False, solution)
        test_wordle("new_york_times", True, solution)
        test_wordle("wordlegame_org", True, solution)

    stop = time.perf_counter()
    print(f"Tests duration {stop - start:.4f}")

if __name__ == "__main__":
    main()
