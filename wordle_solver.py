import time
import itertools
from abc import ABCMeta, abstractmethod

import math
from multiprocessing import Process, Queue, cpu_count

from wordle_utils import progress_bar, ProgressBarMP
from wordle_contexts import LETTERS, WORD_LENGTH

class BaseWordGroup(metaclass = ABCMeta):
    """
    Base class to represent a group of words, and
    calculate statistics on them.
    """
    @abstractmethod
    def __len__(self): pass

    @abstractmethod
    def __contains__(self, val): pass

    @abstractmethod
    def __iter__(self): pass

    def __copy__(self):
        return self.copy()

    def __bool__(self):
        return len(self) > 0

    def __repr__(self):
        return f"<{self.__class__.__name__} with {len(self)} words>"

    @abstractmethod
    def copy(self): pass

class WordGroup(BaseWordGroup):
    """
    Keep statistics on the words for refining solutions and guesses.
    Keeps an "undo" state, so that the word list can be rolled back
    to the previous state if a guess is wrong using reset().
    """
    def __init__(self, word_list):
        # Save word list
        self._word_list = set(word_list)

        # Calculate stats for words
        self.prepare_stats()

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

    def copy(self):
        return self.__class__(self._word_list)

    def prepare_stats(self):
        """Calculate statistics for the current word list"""
        # Word breakdown
        self._word_breakdown = [
            {l: set() for l in LETTERS} for i in range(WORD_LENGTH)]

        for word in self._word_list:
            for index in range(WORD_LENGTH):
                self._word_breakdown[index][word[index]].add(word)

        # Make Word breakdown frozensets
        for index in range(WORD_LENGTH):
            for letter in LETTERS:
                self._word_breakdown[index][letter] = frozenset(
                    self._word_breakdown[index][letter])

        # Word contains
        self._word_contains = {l: set() for l in LETTERS}
        for letter in LETTERS:
            for index in range(WORD_LENGTH):
                self._word_contains[letter].update(
                    self._word_breakdown[index][letter])

        # Make Word contains frozensets
        for letter in LETTERS:
            self._word_contains[letter] = frozenset(self._word_contains[letter])

        # Letter count
        # Create a bucket for each letter and count of that letter in word
        # Note that some buckets will always be empty
        self._letter_count = {
            l: {c: set() for c in range(1, WORD_LENGTH + 1)} for l in LETTERS}

        for word in self._word_list:
            for letter in set(word):
                count = word.count(letter)
                self._letter_count[letter][count].add(word)

        # Make letter count frozensets
        for letter in LETTERS:
            for count in range(1, WORD_LENGTH + 1):
                self._letter_count[letter][count] = frozenset(
                    self._letter_count[letter][count])

    @property
    def excluded_letters(self):
        """Check which letters that can not be part of the solution"""
        # Inefficient method, but seems fast enough
        included_letters = set()
        for word in self:
            included_letters.update(word)
            if len(included_letters) == len(LETTERS):
                # All letters are present
                assert included_letters == set(LETTERS)
                break

        excluded_letters = included_letters.symmetric_difference(LETTERS)
        return excluded_letters

class GuessGroup(WordGroup):
    """
    Use results learned from playing the game to refine possible guesses.
    """
    def filter_guesses(self, excluded_letters):
        """
        Filter out guesses that are not possible based on excluded letters.
        """
        self.prepare_stats()

        # Create a set of all words that contain excluded letters, grouped by count
        suspect_breakdown = {index: set() for index in range(1, WORD_LENGTH + 1)}
        for letter in excluded_letters:
            for word in self._word_contains[letter]:
                count = 0
                for index in range(WORD_LENGTH):
                    if word[index] in excluded_letters:
                        count += 1

                suspect_breakdown[count].add(word)

        # Starting with the words with the most excluded letters
        # Since a word with only excluded letters will return result bbbbb
        # There is no information to be gained from it
        self._word_list.difference_update(suspect_breakdown[WORD_LENGTH])

        for count in range(WORD_LENGTH - 1, 0, -1):
            for word in suspect_breakdown[count]:
                # Check if a word exists that contains all of the non-excluded letters
                superior_words = None
                for index in range(WORD_LENGTH):
                    if word[index] not in excluded_letters:
                        word_set = self._word_breakdown[index][word[index]]

                        if superior_words is None:
                            superior_words = set(word_set)
                        else:
                            superior_words.intersection_update(word_set)

                assert superior_words is not None, \
                    f"All letters in word {word} are excluded, but count is {count}"

                # Remove superior words if they contain excluded letters
                for other_count in range(count, WORD_LENGTH + 1):
                    superior_words.difference_update(suspect_breakdown[other_count])

                if superior_words:
                    # Remove word from list
                    self._word_list.remove(word)

class AllWordsGuessGroup(BaseWordGroup):
    """
    Guess group that contains all possible combinations
    of letters as words. Generates the list on the fly
    to avoid needing to store all of it in memory.
    """
    def __init__(self, excluded_letters = None):
        if excluded_letters is None:
            excluded_letters = set()

        self.excluded_letters = excluded_letters

    def __len__(self):
        return (len(LETTERS) - len(self.excluded_letters)) ** WORD_LENGTH

    def __contains__(self, val):
        if isinstance(val, str) and len(val) == WORD_LENGTH:
            return self.excluded_letters.disjoint(val)
        return False

    def __iter__(self):
        """Iterate over all possible words"""
        # Use product() to create all words of possible letters
        included_letters = self.excluded_letters.symmetric_difference(LETTERS)
        for word in itertools.product(*[included_letters] * WORD_LENGTH):
            yield "".join(word)

    def copy(self):
        return self.__class__(self.excluded_letters)

    def filter_guesses(self, excluded_letters):
        # Simplify save excluded letters
        self.excluded_letters.update(excluded_letters)

class BaseSolutionGroup(WordGroup):
    """
    Keep statistics and manipulation for solutions.
    Keep an internal reset state for repeated filtering.
    """
    def __init__(self, word_list):
        super().__init__(word_list)

        # Setup internal state
        self._prev_word_list = self._word_list.copy()
        self.changed = False

    @abstractmethod
    def filter_solutions(self, word, result):
        """Filter solutions based on the result of the guess"""
        pass

    @abstractmethod
    def guess_rank(self, guess):
        """
        Calculate rank of a word in this group. Higher rank is better guess.
        """
        pass

    def reset(self):
        if self.changed:
            assert self._prev_word_list is not None, \
                "Reset state has never been set, yet word list is changed"
            self._word_list = self._prev_word_list.copy()
            self.changed = False

RESULTS = ["".join(result) for result in itertools.product(*["gyb"] * WORD_LENGTH)]

# You can't have 4 known letters, and 1 incorrectly positioned
RESULTS = [result for result in RESULTS if result.count("y") != 1 or "b" in result]
RESULTS.reverse()

def result_possible(word, result):
    # If a letter is duplicated, then the first instance must be found
    absent = set()

    for index in range(WORD_LENGTH):
        if result[index] == "b":
            absent.add(word[index])
        elif result[index] == "y":
            # Letter Present, not possible for it to have been previously absent
            if word[index] in absent:
                return False
    return True

class SolutionGroup(BaseSolutionGroup):
    """
    Use results learned from playing the game to refine possible solutions.
    """
    def filter_solutions(self, word, result):
        if self.changed:
            # If the word list has changed, update the stats
            self._prev_word_list = self._word_list.copy()
            self.prepare_stats()
        else:
            # Otherwise, mark the list as changed,
            # as it is about to be changed
            self.changed = True

        for index in range(WORD_LENGTH):
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
                for index in range(WORD_LENGTH):
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
        Uses internal reset state.
        """
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
                f"Results have overlapping words: " \
                f"{processed_words.intersection(self._word_list)}"

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

    def _guess_rank_mp(self, guess_group, queue):
        best_guesses = []
        best_rank = None

        for word in guess_group:
            rank, foil = self.guess_rank(word)

            if not best_rank or rank < best_rank:
                best_rank = rank
                best_guesses = [word]

            elif rank == best_rank:
                best_guesses.append(word)

        queue.put((best_guesses, best_rank))

def best_guesses(guess_group, solution_group, progress = True, mp = True):
    # Find the best next word
    best_guesses = []
    best_rank = None

    # Do not consider words that use letters that are already excluded
    start = time.perf_counter()
    full_word_list_count = len(guess_group)
    excluded_letters = solution_group.excluded_letters
    guess_group.filter_guesses(excluded_letters)
    stop = time.perf_counter()

    # Say how many words were filtered out, if there are excluded letters
    if progress and excluded_letters:
        print(f"Filtered {full_word_list_count} words down to "
            f"{len(guess_group)} in {stop - start:.4f} secs")

    if mp is True:
        mp = cpu_count()

    if mp:
        # Use multiprocessing to accelerate processing
        if progress:
            print(f"Calculating Guesses using {mp} processes...")

        processes = []
        chunksize = math.ceil(len(guess_group) / mp)
        queue = Queue()
        progress_bar_mp = ProgressBarMP(persist = progress)

        # So we can directly index it
        guess_list = list(guess_group)

        for i in range(mp):
            process = Process(target = solution_group.copy()._guess_rank_mp,
                args = (progress_bar_mp.worker_loop(guess_list[chunksize * i: chunksize * (i + 1)]),
                        queue))

            processes.append(process)

        for process in processes:
            process.start()

        progress_bar_mp.parent_loop()

        for process in processes:
            process.join()

        # Collect results
        while not queue.empty():
            guesses, rank = queue.get()

            if not best_rank or rank < best_rank:
                best_rank = rank
                best_guesses = guesses

            elif rank == best_rank:
                best_guesses.extend(guesses)
    else:
        # Use single process
        for word in progress_bar(guess_group, persist = progress):
            rank, foil = solution_group.guess_rank(word)

            if not best_rank or rank < best_rank:
                best_rank = rank
                best_guesses = [word]

            elif rank == best_rank:
                best_guesses.append(word)

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

    stop = time.perf_counter()

    if progress:
        print(f"Calculated Guesses in {stop - start:.3f} secs")

    return best_guesses, best_rank
