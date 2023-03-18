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

def wordle_result(guess, solution, context):
    """Given a guess and solution, generate the coloring wordle would show"""
    # Result calculation is basically check if guess letter matches
    # solution, but there is some complexity to account for duplicate
    # letters.
    assert len(guess) == context.word_length, \
        f"guess {guess!r} is not {context.word_length} letters"
    assert len(solution) == context.word_length, \
        f"solution {solution!r} is not {context.word_length} letters"

    # "u" is unassigned temporary value
    result = ["u"] * context.word_length

    # First Pass, Correct and Absent
    for index in range(context.word_length):
        if guess[index] == solution[index]:
            # Correct
            result[index] = "g"
        elif guess[index] not in solution:
            # Absent
            result[index] = "b"

    # Second Pass Count Remaining Letters
    # Count letters
    solution_letters = {l: 0 for l in context.letters}
    for index in range(context.word_length):
        if result[index] != "g":
            solution_letters[solution[index]] += 1

    # Third Pass
    # Mark Present
    for index in range(context.word_length):
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

def wordle_test(solution, context, progress = True, mp = True):
    """Play wordle, and time how long it takes.
       If no solution is provided, a worst case scenario is calculated.
       The worst case solution is known as the "foil"
    """
    guess_group = context.get_guess_group()
    solution_group = context.get_solution_group()

    start = time.perf_counter()
    while True:
        if  1 <= len(solution_group) <= 2:
            # Only two or less words
            # Best guess is either of the words
            guess = min(solution_group)
        else:
            # There should be a solution found
            assert len(solution_group) != 0, "There are no remaining solutions"

            # Calculate best guess
            rank, guesses, foils = wordle_solver.best_guesses(
                guess_group, solution_group, progress = None if progress else False, mp = mp)
            guess = min(guesses)

        # If no solution, use foil
        if solution:
            result = wordle_result(guess, solution, context)
        else:
            rank, result = solution_group.guess_rank(guess)

        if progress:
            print(wordle_coloring(guess, result))

        # Add word result to context
        context.next_turn(guess, result)

        if result == "g" * context.word_length:
            if not solution:
                solution = guess

            if progress:
                print("Success!")
            break

        # Find number of words remaining
        # Track prior count to see if solutions were removed
        solution_count = len(solution_group)
        solution_group.filter_solutions(guess, result)

        # Make sure solutions were removed
        assert len(solution_group) < solution_count, f"No solutions eliminated for guess {guess!r}"

    stop = time.perf_counter()

    if progress:
        print(
            f"Test: {context.name} Naive: {context.naive} "
            f"Solution: {solution} Turns: {context.turns} Duration: {stop - start:.4f} secs\n")

    turns = context.turns
    context.reset()
    return turns

def main():
    init()

    start = time.perf_counter()
    for solution in [None, "magic", "abort", "krill", "staff"]:
        wordle_test(solution, wordle_contexts.Context("new_york_times", False))
        wordle_test(solution, wordle_contexts.Context("wordlegame_org", False, 5))
        wordle_test(solution, wordle_contexts.Context("new_york_times", True))
        wordle_test(solution, wordle_contexts.Context("wordlegame_org", True, 5))

    stop = time.perf_counter()
    print(f"Tests Duration {stop - start:.4f} secs")

if __name__ == "__main__":
    main()
