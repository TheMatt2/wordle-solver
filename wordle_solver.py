import time
import itertools

word_length = 5
letters = "abcdefghijklmnopqrstuvwxyz"

class WordStats:
    """
    Track the list of possible solutions, and keep statistics on the words.
    Word Stats also keeps an "Undo" state, so that the word list can be rolled back
    to the previous state if a guess is wrong using reset().
    """
    def __init__(self, word_list):
        # Setup rollback state
        self._prev_word_list = set(word_list)
        self.word_list = self._prev_word_list.copy()
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
        return len(self.word_list)

    def __contains__(self, val):
        return val in self.word_list

    def __bool__(self):
        return bool(self.word_list)

    def __iter__(self):
        return iter(self.word_list)

    def __repr__(self):
        return f"<WordStats with {len(self)} words>"

    def calculate_stats(self):
        """Calculate statistics for the current word list"""
        # Word breakdown
        self._word_breakdown = [
            {v: set() for v in letters}
             for i in range(word_length)]

        for word in self.word_list:
            for index in range(word_length):
                self._word_breakdown[index][word[index]].add(word)

        # Word contains
        self._word_contains = {v: set() for v in letters}
        for letter in letters:
            for index in range(word_length):
                self._word_contains[letter].update(self._word_breakdown[index][letter])

        # Letter count
        # Create a bucket for each letter and count of that letter in word
        # Note that some buckets will always be empty
        self._letter_count = {v: {k: set() for k in range(1, word_length + 1)} for v in letters}

        for word in self.word_list:
            for letter in set(word):
                letter_count = word.count(letter)
                self._letter_count[letter][letter_count].add(word)

    def filter(self, word, result):
        if self.changed:
            self._prev_word_list = self.word_list.copy()
            self.calculate_stats()
        else:
            self.changed = True

        for index in range(word_length):
            if result[index] == "g":
                # Keep only words that have that letter in that position
                self.word_list.intersection_update(self._word_breakdown[index][word[index]])
            else:
                # Keep only words that don't have that letter in that position
                self.word_list.difference_update(self._word_breakdown[index][word[index]])

                if result[index] == "y":
                    # Keep only words that have that letter somewhere
                    self.word_list.intersection_update(self._word_contains[word[index]])
                else:
                    assert result[index] == "b"

                    # If letter does not appear anywhere else in the word,
                    # then keep only works without the letter
                    if not (word[index] in word[:index] or word[index] in word[index + 1:]):
                        self.word_list.difference_update(self._word_contains[word[index]])

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
                    self.word_list.intersection_update(
                        self._letter_count[letter][present_count + correct_count])
                elif absent_count and not present_count and not correct_count:
                    # Letter does not occur in word
                    self.word_list.difference_update(self._word_contains[letter])
                else:
                    assert not absent_count
                    # No strict limit on the number of letters, but we can set a lower limit
                    for count in range(1, present_count + correct_count):
                        self.word_list.difference_update(self._letter_count[letter][count])

    @property
    def excluded_letters(self):
        """Check which letters that can not be part of the solution"""
        # Very inefficient method, hack for now
        included_letters = set()
        for word in self:
            included_letters.update(word)

        return included_letters.symmetric_difference(letters)

    def reset(self):
        if self.changed:
            self.word_list = self._prev_word_list.copy()
            self.changed = False

results = ["".join(result) for result in itertools.product(*["gyb"] * word_length)]

# You can't have 4 known letters, and 1 incorrectly positioned
results = [result for result in results if result.count("y") != 1 or "b" in result]
results.reverse()

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

def word_rank(word, word_stats):
    # If word has repeated letters, right gives the same amount of information, positions gives a bit less
    # wrong gives a fair bit less information
    # Rank = Sum [Pr[permutation] * information]
    # G is correct
    # Y is present
    # B is absent
    assert word_stats

    rank = 0
    total = 0

    words = set()
    for result in results:
        # assert word_stats
        word_stats.word_list.difference_update(words)
        if not word_stats:
            word_stats.changed = True
            word_stats.reset()
            break

        # Check if this result can occur
        if not result_possible(word, result):
            continue

        # Calculate number of words that remain if this result occurs
        word_stats.filter(word, result)

        # Calculate the percent of words that fall in this group
        part = len(word_stats)
        total += part # Sanity check

        assert words.isdisjoint(word_stats.word_list), \
            f"Results have overlapping words: {words.intersection(word_stats.word_list)}"
        words.update(word_stats.word_list)

        # Rank is the highest count of words that can result
        if part > rank:
            rank = part
            foil = result

        assert(len(words) == total)
        word_stats.reset()

    assert rank
    assert total == len(word_stats), \
        f"total = {total} and remaining words {len(word_stats)} differ for word {word}"

    # Foil is the result that keeps the most combinations
    return rank, foil

def gen_possible_words(word, excluded_letters):
    for index in range(len(word)):
        if word[index] in excluded_letters:
            prefix = word[:index]
            suffix = word[index + 1:]

            for letter in letters:
                # Don't generate the same word
                if letter != word[index]:
                    yield prefix + letter + suffix

            if suffix:
                for letter in excluded_letters.symmetric_difference(letters):
                    for postfix in gen_possible_words(suffix, excluded_letters):
                        yield f"{prefix}{letter}{postfix}"

def best_guesses(word_list, word_stats, progress = True):
    # Find the best next word
    best_guesses = []
    best_rank = None

    # Do not consider words that use letters that are already excluded
    start = time.time()
    excluded_letters = word_stats.excluded_letters
    full_word_list_count = len(word_list)
    word_list = set(word_list)

    for word in list(word_list):
        if excluded_letters.isdisjoint(word):
            continue

        for maybe_word in gen_possible_words(word, excluded_letters):
            if maybe_word in word_list:
                word_list.remove(word)
                break

    stop = time.time()

    if progress:
        print(f"Excluded {full_word_list_count} words down to "
            f"{len(word_list)} in {stop - start:.4f} seconds")

    start = time.time()
    for i, word in enumerate(word_list):
        if progress and i % 100 == 0:
            print(f"Progress: {i * 100 / len(word_list):.2f}% ({i} / {len(word_list)})", end = "\r")

        rank, foil = word_rank(word, word_stats)

        if not best_rank or rank < best_rank:
            best_rank = rank
            best_guesses = [word]

        elif rank == best_rank:
            best_guesses.append(word)

    if progress:
        print(f"Progress: 100.00% ({len(word_list)} / {len(word_list)})")

    # If a guess is in the solution set, that actually makes it
    # better than any other option
    guess_in_solutions = False
    for guess in best_guesses:
        if guess in word_stats:
            guess_in_solutions = True
            break

    if guess_in_solutions:
        # Filter down to only guesses in solutions
        best_guesses = [
            guess for guess in best_guesses if guess in word_stats]
    stop = time.time()

    if progress:
        print(f"Calculated Guesses in {stop - start:.3f} seconds")

    return best_guesses, best_rank
