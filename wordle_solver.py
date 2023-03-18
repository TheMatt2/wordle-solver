import time
import itertools
from abc import ABCMeta, abstractmethod

import math
import concurrent.futures
from multiprocessing import cpu_count

from wordle_utils import progress_bar, ProgressBarMP, wait_exception_or_completed, chunked

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
    """
    def __init__(self, word_list, context = None):
        if context is None:
            # Only allow context to be None if word_list is a WordGroup
            if not isinstance(word_list, WordGroup):
                raise TypeError(
                    "argument 'context' is required if word_list is not a WordGroup()")

        elif isinstance(word_list, WordGroup):
            # If word_list is a WordGroup, context should be none
            raise TypeError(
                "argument 'context' is not allowed if word_list is a WordGroup()")

        if isinstance(word_list, WordGroup):
            # Optimized copy initializer

            # A copy is likely going to be modified
            # and modifying using stats, so precompute stats
            word_list._prepare_stats()

            assert not word_list._changed, \
                f"{word_list.__class__.__name__} is changed after preparing stats"
            self._changed = word_list._changed
            self._word_list = word_list._word_list.copy()

            # As stats are only ever used immutably, just add without copy
            self._word_breakdown = word_list._word_breakdown
            self._word_contains = word_list._word_contains
            self._letter_count = word_list._letter_count
            self.context = word_list.context

        else:
            # Save word list
            self._word_list = set(word_list)

            # Make changed so stats will be calculate if needed
            self._changed = True
            self.context = context

    def __len__(self):
        return len(self._word_list)

    def __contains__(self, val):
        return val in self._word_list

    def __bool__(self):
        return bool(self._word_list)

    def __iter__(self):
        return iter(self._word_list)

    def __getstate__(self):
        # For pickling
        # Do not save stats, as they are useless if changed
        # Even if not changed, it is still likely faster to recalculate
        return {"_word_list": self._word_list, "_changed": True, "context": self.context}

    def copy(self):
        return self.__class__(self)

    def _prepare_stats(self):
        """Calculate statistics for the current word list"""
        if not self._changed:
            # No need to recalculate statistics
            return

        # Word breakdown
        self._word_breakdown = [
            {l: set() for l in self.context.letters} for i in range(self.context.word_length)]

        for word in self._word_list:
            for index in range(self.context.word_length):
                self._word_breakdown[index][word[index]].add(word)

        # Make Word breakdown frozensets
        for index in range(self.context.word_length):
            for letter in self.context.letters:
                self._word_breakdown[index][letter] = frozenset(
                    self._word_breakdown[index][letter])

        # Word contains
        self._word_contains = {l: set() for l in self.context.letters}
        for letter in self.context.letters:
            for index in range(self.context.word_length):
                self._word_contains[letter].update(
                    self._word_breakdown[index][letter])

        # Make Word contains frozensets
        for letter in self.context.letters:
            self._word_contains[letter] = frozenset(self._word_contains[letter])

        # Letter count
        # Create a bucket for each letter and count of that letter in word
        # Note that some buckets will always be empty
        self._letter_count = {
            l: {c: set() for c in range(1, self.context.word_length + 1)} for l in self.context.letters}

        for word in self._word_list:
            for letter in set(word):
                count = word.count(letter)
                self._letter_count[letter][count].add(word)

        # Make letter count frozensets
        for letter in self.context.letters:
            for count in range(1, self.context.word_length + 1):
                self._letter_count[letter][count] = frozenset(
                    self._letter_count[letter][count])

        # Mark as not changed anymore
        self._changed = False

    @property
    def excluded_letters(self):
        """Check which letters never appear in the word group"""
        # Calculate excluded letters using breakdown
        self._prepare_stats()
        excluded_letters = set()
        for letter, word_set in self._word_contains.items():
            if not len(word_set):
                excluded_letters.add(letter)
        return excluded_letters

class GuessGroup(WordGroup):
    """
    Use results learned from playing the game to refine possible guesses.
    """
    def filter_guesses(self, excluded_letters):
        """
        Filter out guesses that are not possible based on excluded letters.
        """
        self._prepare_stats()

        # Get current word count
        word_count = len(self)

        # Create a set of all words that contain excluded letters, grouped by count
        suspect_breakdown = {index: set() for index in range(1, self.context.word_length + 1)}
        for letter in excluded_letters:
            for word in self._word_contains[letter]:
                count = 0
                for index in range(self.context.word_length):
                    if word[index] in excluded_letters:
                        count += 1

                suspect_breakdown[count].add(word)

        # Starting with the words with the most excluded letters
        # Since a word with only excluded letters will return result bbbbb
        # There is no information to be gained from it
        self._word_list.difference_update(suspect_breakdown[self.context.word_length])

        for count in range(self.context.word_length - 1, 0, -1):
            for word in suspect_breakdown[count]:
                # Check if a word exists that contains all of the non-excluded letters
                superior_words = None
                for index in range(self.context.word_length):
                    if word[index] not in excluded_letters:
                        word_set = self._word_breakdown[index][word[index]]

                        if superior_words is None:
                            superior_words = set(word_set)
                        else:
                            superior_words.intersection_update(word_set)

                assert superior_words is not None, \
                    f"All letters in word {word} are excluded, but count is {count}"

                # Remove superior words if they contain excluded letters
                for other_count in range(count, self.context.word_length + 1):
                    superior_words.difference_update(suspect_breakdown[other_count])

                if superior_words:
                    # Remove word from list
                    self._word_list.remove(word)

        # Mark as change if guesses were eliminated
        self._changed = word_count != len(self)

class AllWordsGuessGroup(BaseWordGroup):
    """
    Guess group that contains all possible combinations
    of letters as words. Generates the list on the fly
    to avoid needing to store all of it in memory.
    """
    def __init__(self, context, excluded_letters = None):
        if excluded_letters is None:
            excluded_letters = set()

        self.excluded_letters = excluded_letters
        self.context = context

    def __len__(self):
        return (len(self.context.letters) - len(self.excluded_letters)) ** self.context.word_length

    def __contains__(self, val):
        if isinstance(val, str) and len(val) == self.context.word_length:
            return self.excluded_letters.disjoint(val)
        return False

    def __iter__(self):
        """Iterate over all possible words"""
        # Use product() to create all words of possible letters
        included_letters = self.excluded_letters.symmetric_difference(self.context.letters)
        for word in itertools.product(*[included_letters] * self.context.word_length):
            yield "".join(word)

    def copy(self):
        return self.__class__(self.excluded_letters)

    def filter_guesses(self, excluded_letters):
        # Simplify save excluded letters
        self.excluded_letters.update(excluded_letters)

class BaseSolutionGroup(WordGroup):
    """
    Keep statistics and manipulation for solutions.
    """
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

def result_possible(word, result, context):
    # If a letter is duplicated, then the first instance must be found
    absent = set()

    for index in range(context.word_length):
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
    # Create list of possible results
    _RESULTS = {}

    @property
    def results(self):
        """Get list of possible results"""
        if self.context.word_length in self._RESULTS:
            return self._RESULTS[self.context.word_length]

        # Calculate results
        results = ["".join(result) for result in itertools.product(*["gyb"] * self.context.word_length)]

        # You can't have 4 known letters, and 1 incorrectly positioned
        results = [result for result in results if result.count("y") != 1 or "b" in result]
        results.reverse()
        self._RESULTS[self.context.word_length] = results
        return results

    def filter_solutions(self, word, result):
        """Remove solutions that are not consistant with word and result."""
        # Update statistics, if needed
        self._prepare_stats()

        # Get current word count
        word_count = len(self)

        for index in range(self.context.word_length):
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
                for index in range(self.context.word_length):
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

        # Mark as change if solutions were eliminated
        self._changed = word_count != len(self)

    def guess_rank(self, guess):
        """
        Calculate rank of a word in this group.
        Uses heuristic of max partition size to rank guesses.
        """
        rank = 0
        foil = None

        partitions = 0
        for result, solution_part in self.partition(guess):
            partitions += 1

            part = len(solution_part)
            if part > rank:
                rank = part
                foil = result

        assert rank, f"No partitions found for {guess}"

        # Use the number of partitions as a tie breaker
        # Since lower rank is better, use 1 / partitions
        # Since 0 < 1 / (partitions + 1) < 1, just add partitions as a decimal
        # (Using p + 1 to avoid the case where partitions is 1)
        rank +=  1 / (partitions + 1)

        # Foil is the result that keeps the most combinations
        return rank, foil

    def partition(self, guess):
        """
        Generate partitions solutions for each possible result of guess.
        """
        # If word has repeated letters, right gives the same amount of information,
        # positions gives a bit less, wrong gives a fair bit less information
        # G is correct
        # Y is present
        # B is absent
        if __debug__:
            # Total is tracked as a sanity check
            total = 0

        # Words that are already returned from filter_solutions() will not be
        # returned by other result. So keep a list of processed words, and don't
        # consider them for further filtering.
        processed_words = set()
        for result in self.results:
            # Check if this result can occur
            if not result_possible(guess, result, self.context):
                continue

            # If processed words contains all words, we are done
            if len(self) == len(processed_words):
                # No words left to process
                break

            # Create copy of solution group to process
            solution_part = self.copy()

            # Remove already processed words. If a word appeared in a
            # prevous result, word comparison, then it won't appear again
            solution_part._word_list.difference_update(processed_words)

            # Calculate number of words that remain if this result occurs
            solution_part.filter_solutions(guess, result)

            # Calculate the percent of words that fall in this group
            if __debug__:
                total += len(solution_part) # Sanity check

            assert processed_words.isdisjoint(solution_part._word_list), \
                f"Results have overlapping words: " \
                f"{processed_words.intersection(solution_part._word_list)}"

            processed_words.update(solution_part._word_list)

            # Yield the partition, if non-empty
            if solution_part:
                yield result, solution_part

            assert len(processed_words) == total

        assert total == len(self), \
            f"total = {total} and remaining words {len(self)} differ for guess {guess}"

    def _guess_rank_mp(self, guess_group):
        assert guess_group, "No guesses to rank"

        best_rank = None
        best_guesses = None
        best_foils = None

        for guess in guess_group:
            rank, foil = self.guess_rank(guess)

            if not best_rank or rank < best_rank:
                best_rank = rank
                best_guesses = [guess]
                best_foils = [foil]

            elif rank == best_rank:
                best_guesses.append(guess)
                best_foils.append(foil)

        return best_rank, best_guesses, best_foils

def filter_guesses(guess_group, solution_group, progress = True):
    """
    Remove guesses that are strictly worse than other guess words
    That way we don't need to spend time checking them as solutions
    """
    # Do not consider words that use letters that are already excluded
    start = time.perf_counter()
    full_word_list_count = len(guess_group)
    excluded_letters = solution_group.excluded_letters
    guess_group.filter_guesses(excluded_letters)
    stop = time.perf_counter()

    # Say how many words were filtered out, if there are excluded letters
    if progress and full_word_list_count != len(guess_group):
        print(f"Filtered {full_word_list_count} words down to "
            f"{len(guess_group)} in {stop - start:.4f} secs")

def best_guesses(guess_group, solution_group, progress = True, mp = True, cache = True):
    """Generate the best guesses for the words and solutions."""
    if guess_group.context != solution_group.context:
        raise ValueError("Guess and solution groups must have the same context")

    if cache:
        # Use context to check if results can be returned from the cache
        context = guess_group.context
        best_rank, best_guesses, best_foils = context.load_guesses()
        if best_rank is not None:
            return best_rank, best_guesses, best_foils

    if mp and len(guess_group) * len(solution_group) < 60000:
        # Multiprocessing is not worth it for small problems
        mp = False

    # Find the best next word
    best_rank = None
    best_guesses = None
    best_foils = None

    # Remove extra guesses
    filter_guesses(guess_group, solution_group, progress)

    if mp is True:
        mp = cpu_count()

    start = time.perf_counter()
    if mp:
        # Use multiprocessing to accelerate processing
        if progress:
            print(f"Calculating Guesses using {mp} processes...")

        with ProgressBarMP(len(guess_group), persist = progress,
                enabled = progress is not False) as progress_bar_mp, \
                concurrent.futures.ProcessPoolExecutor(mp) as executor:

                # Process for each batch
                fs = []
                for guess_chunk in chunked(guess_group, mp):
                    future = executor.submit(solution_group._guess_rank_mp,
                        progress_bar_mp.worker_loop(guess_chunk))
                    fs.append(future)

                progress_bar_mp.parent_loop(lambda x: wait_exception_or_completed(fs, x))

                for future in fs:
                    rank, guesses, foils = future.result()

                    if not best_rank or rank < best_rank:
                        best_rank = rank
                        best_guesses = guesses
                        best_foils = foils

                    elif rank == best_rank:
                        best_guesses.extend(guesses)
                        best_foils.extend(foils)

    else:
        # Use single process
        for guess in progress_bar(guess_group, persist = progress,
                enabled = progress is not False):

            rank, foil = solution_group.guess_rank(guess)

            if not best_rank or rank < best_rank:
                best_rank = rank
                best_guesses = [guess]
                best_foils = [foil]

            elif rank == best_rank:
                best_guesses.append(guess)
                best_foils.append(foil)

    # If a guess is in the solution set, that actually makes it
    # better than any other option. Filter down to only guesses in solutions
    restricted_best_guesses = []
    restricted_best_foils = []
    for guess, foil in zip(best_guesses, best_foils):
        if guess in solution_group:
            restricted_best_guesses.append(guess)
            restricted_best_foils.append(foil)

    if restricted_best_guesses:
        best_guesses = restricted_best_guesses
        best_foils = restricted_best_foils

    stop = time.perf_counter()
    if progress:
        print(f"Calculated Guesses in {stop - start:.3f} secs")

    assert len(best_guesses) == len(best_foils), "Number of guesses and foils do not match"

    if cache:
        # Add results to cache
        context = guess_group.context
        context.save_guesses(best_rank, best_guesses, best_foils)

    return best_rank, best_guesses, best_foils
