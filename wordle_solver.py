import time
import itertools

word_length = 5
letters = "abcdefghijklmnopqrstuvwxyz"

class WordGroup:
    """
    Keep statistics on the words for refining solutions and guesses.
    Keeps an "undo" state, so that the word list can be rolled back
    to the previous state if a guess is wrong using reset().
    """
    def __init__(self, word_list):
        # Setup rollback state
        self._prev_word_list = set(word_list)
        self._word_list = self._prev_word_list.copy()
        self.changed = False

        # Internal statistics
        # Must be internal, because they are only calculated as needed
        # and backup state is lost

        # actually initialized in calculate_stats()
        self._word_breakdown = None
        self._word_contains = None
        self._letter_count = None

        # Calculate stats for words
        self.calculate_stats()

    def __len__(self):
        return len(self._word_list)

    def __contains__(self, val):
        return val in self._word_list

    def __bool__(self):
        return bool(self._word_list)

    def __iter__(self):
        return iter(self._word_list)

    def __repr__(self):
        return f"<WordStats with {len(self)} words>"

    def calculate_stats(self):
        """Calculate statistics for the current word list"""
        # Word breakdown
        self._word_breakdown = [
            {l: set() for l in letters}
             for i in range(word_length)]

        for word in self._word_list:
            for index in range(word_length):
                self._word_breakdown[index][word[index]].add(word)

        # Make Word breakdown frozensets
        for index in range(word_length):
            for letter in letters:
                self._word_breakdown[index][letter] = frozenset(self._word_breakdown[index][letter])

        # Word contains
        self._word_contains = {l: set() for l in letters}
        for letter in letters:
            for index in range(word_length):
                self._word_contains[letter].update(self._word_breakdown[index][letter])

        # Make Word contains frozensets
        for letter in letters:
            self._word_contains[letter] = frozenset(self._word_contains[letter])

        # Letter count
        # Create a bucket for each letter and count of that letter in word
        # Note that some buckets will always be empty
        self._letter_count = {l: {c: set() for c in range(1, word_length + 1)} for l in letters}

        for word in self._word_list:
            for letter in set(word):
                count = word.count(letter)
                self._letter_count[letter][count].add(word)

        # Make letter count frozensets
        for letter in letters:
            for count in range(1, word_length + 1):
                self._letter_count[letter][count] = frozenset(self._letter_count[letter][count])

    @property
    def excluded_letters(self):
        """Check which letters that can not be part of the solution"""
        # Very inefficient method, hack for now
        included_letters = set()
        for word in self:
            included_letters.update(word)
            if len(included_letters) == len(letters):
                # All letters are present
                assert included_letters == set(letters)
                break

        return included_letters.symmetric_difference(letters)

    def reset(self):
        if self.changed:
            self._word_list = self._prev_word_list.copy()
            self.changed = False

# def gen_possible_words(word, excluded_letters):
#     for index in range(len(word)):
#         if word[index] in excluded_letters:
#             prefix = word[:index]
#             suffix = word[index + 1:]

#             for letter in letters:
#                 # Don't generate the same word
#                 if letter != word[index]:
#                     yield f"{prefix}{letter}{suffix}"

#             if suffix:
#                 for letter in excluded_letters.symmetric_difference(letters):
#                     for postfix in gen_possible_words(suffix, excluded_letters):
#                         yield f"{prefix}{letter}{postfix}"

class GuessGroup(WordGroup):
    """
    Use results learned from playing the game to refine possible guesses.
    """
    # def filter_guesses(self, excluded_letters):
    #     # Filter out guesses that are not possible
    #     # based on the result
    #     # This is a very inefficient method, but it works
    #     for word in sorted(self._word_list):
    #         if excluded_letters.isdisjoint(word):
    #             continue

    #         for maybe_word in gen_possible_words(word, excluded_letters):
    #             if maybe_word in self._word_list:
    #                 self._word_list.remove(word)
    #                 break

    def filter_guesses(self, excluded_letters):
        if self.changed:
            self._prev_word_list = self._word_list.copy()
            self.calculate_stats()
        else:
            self.changed = True

        # Filter out guesses that are not possible
        # based on the result
        # Create a set of all words that contain excluded letters, grouped by count
        suspect_breakdown = {index: set() for index in range(1, word_length + 1)}
        for letter in excluded_letters:
            for word in self._word_contains[letter]:
                count = 0
                for index in range(word_length):
                    if word[index] in excluded_letters:
                        count += 1

                suspect_breakdown[count].add(word)

        # Starting with the words with the most excluded letters
        # Since a word with only excluded letters will return result bbbbb
        # There is no information to be gained from it
        self._word_list.difference_update(suspect_breakdown[word_length])

        for count in range(word_length - 1, 0, -1):
            for word in suspect_breakdown[count]:
                # Check if a word exists that contains all of the non-excluded letters
                superior_words = None
                for index in range(word_length):
                    if word[index] not in excluded_letters:
                        word_set = self._word_breakdown[index][word[index]]

                        if superior_words is None:
                            superior_words = set(word_set)
                        else:
                            superior_words.intersection_update(word_set)

                assert superior_words is not None, \
                    f"All letters in word {word} are excluded, but count is {count}"

                # Remove superior words if they contain excluded letters
                for other_count in range(count, word_length + 1):
                    superior_words.difference_update(suspect_breakdown[other_count])

                if superior_words:
                    # Remove word from list
                    self._word_list.remove(word)

RESULTS = ["".join(result) for result in itertools.product(*["gyb"] * word_length)]

# You can't have 4 known letters, and 1 incorrectly positioned
RESULTS = [result for result in RESULTS if result.count("y") != 1 or "b" in result]
RESULTS.reverse()

def result_possible(word, result):
    # If a letter is duplicated, then the first instance must be found
    absent = set()

    for index in range(word_length):
        if result[index] == "b":
            absent.add(word[index])
        elif result[index] == "y":
            # Letter Present, not possible for it to have been previously absent
            if word[index] in absent:
                return False
    return True

class SolutionGroup(GuessGroup):
    """
    Use results learned from playing the game to refine possible solutions.
    """
    def filter_solutions(self, word, result):
        if self.changed:
            self._prev_word_list = self._word_list.copy()
            self.calculate_stats()
        else:
            self.changed = True

        for index in range(word_length):
            if result[index] == "g":
                # Keep only words that have that letter in that position
                self._word_list.intersection_update(self._word_breakdown[index][word[index]])
            else:
                # Keep only words that don't have that letter in that position
                self._word_list.difference_update(self._word_breakdown[index][word[index]])

                if result[index] == "y":
                    # Keep only words that have that letter somewhere
                    self._word_list.intersection_update(self._word_contains[word[index]])
                else:
                    assert result[index] == "b"

                    # If letter does not appear anywhere else in the word,
                    # then keep only works without the letter
                    if not (word[index] in word[:index] or word[index] in word[index + 1:]):
                        self._word_list.difference_update(self._word_contains[word[index]])

        # Filter further for repeated letters
        for letter in set(word):
            if word.count(letter) > 1:
                # A letter occurs multple times. Figure out the relationship it has with the solution
                absent_count = 0
                present_count = 0
                correct_count = 0

                indexes = []
                for index in range(word_length):
                    if word[index] != letter:
                        continue

                    indexes.append(index)
                    if result[index] == "g":
                        correct_count += 1
                    elif result[index] == "y":
                        present_count += 1
                    else:
                        assert result[index] == "b"
                        absent_count += 1

                if absent_count and (present_count or correct_count):
                    # The word occurs more times in this word than the solution
                    # Restrict count
                    self._word_list.intersection_update(
                        self._letter_count[letter][present_count + correct_count])
                elif absent_count and not present_count and not correct_count:
                    # Letter does not occur in word
                    self._word_list.difference_update(self._word_contains[letter])
                else:
                    assert not absent_count
                    # No strict limit on the number of letters, but we can set a lower limit
                    for count in range(1, present_count + correct_count):
                        self._word_list.difference_update(self._letter_count[letter][count])

    def guess_rank(self, guess):
        """
        Calculate rank of a word in this group. Higher rank means better guess.
        Uses interal reset state."""
        # If word has repeated letters, right gives the same amount of information,
        # positions gives a bit less, wrong gives a fair bit less information
        # Rank = Sum [Pr[permutation] * information]
        # G is correct
        # Y is present
        # B is absent
        rank = 0
        if __debug__:
            # Total is tracked as a sanity check
            total = 0

        # Words that are already returned from filter_solutions()
        # will not be returned by other result.
        # So keep a list of processed words, and don't consider them
        # for further filtering.
        processed_words = set()
        for result in RESULTS:
            self._word_list.difference_update(processed_words)
            if not self:
                # Force this to marked as changed
                self.changed = True
                self.reset()
                break

            # Check if this result can occur
            if not result_possible(guess, result):
                continue

            # Calculate number of words that remain if this result occurs
            self.filter_solutions(guess, result)

            # Calculate the percent of words that fall in this group
            part = len(self)
            if __debug__:
                total += part # Sanity check

            assert processed_words.isdisjoint(self._word_list), \
                f"Results have overlapping words: {processed_words.intersection(self._word_list)}"
            processed_words.update(self._word_list)

            # Rank is the highest count of words that can result
            if part > rank:
                rank = part
                foil = result

            assert len(processed_words) == total
            self.reset()

        assert rank
        assert total == len(self), \
            f"total = {total} and remaining words {len(self)} differ for guess {guess}"

        # Foil is the result that keeps the most combinations
        return rank, foil

    # def filter_guesses(self, excluded_letters):
    #     """
    #     Dummy function, in case we are playing hard mode,
    #     where all guesses must be possible solutions.
    #     """
    #     # Filtering is already done by filter_solutions()
    #     # No need to filter further
    #     self.changed = True


def best_guesses(guess_group, solution_group, progress = True):
    # Find the best next word
    best_guesses = []
    best_rank = None

    # Do not consider words that use letters that are already excluded
    start = time.time()
    full_word_list_count = len(guess_group)
    guess_group.filter_guesses(solution_group.excluded_letters)
    stop = time.time()

    if progress:
        print(f"Filtered {full_word_list_count} words down to "
            f"{len(guess_group)} in {stop - start:.4f} seconds")

    start = time.time()
    for i, word in enumerate(guess_group):
        if progress and i % 100 == 0:
            print(f"Progress: {i * 100 / len(guess_group):.2f}% ({i} / {len(guess_group)})", end = "\r")

        rank, foil = solution_group.guess_rank(word)

        if not best_rank or rank < best_rank:
            best_rank = rank
            best_guesses = [word]

        elif rank == best_rank:
            best_guesses.append(word)

    if progress:
        print(f"Progress: 100.00% ({len(guess_group)} / {len(guess_group)})")

    # If a guess is in the solution set, that actually makes it
    # better than any other option
    guess_in_solutions = False
    for guess in best_guesses:
        if guess in solution_group:
            guess_in_solutions = True
            break

    if guess_in_solutions:
        # Filter down to only guesses in solutions
        best_guesses = [
            guess for guess in best_guesses if guess in solution_group]
    stop = time.time()

    if progress:
        print(f"Calculated Guesses in {stop - start:.3f} seconds")

    return best_guesses, best_rank
