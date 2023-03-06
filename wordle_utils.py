"""
Utility functions to help with display progress and
time taken.
"""
import sys
import time

import concurrent.futures
from functools import wraps
from multiprocessing import Manager

try:
    from colorama.ansi import clear_line
except NameError:
    clear_line = lambda: None

def progress_bar(iterable, ticks = 10, delay = 0.5,
                persist = False, enabled = None,
                file = None, timer = time.perf_counter):
    """
    Show a simply progress bar for iterable.
    iterable: The object to return items from.
    ticks: Maximum number of updates per second.
    delay: Delay in seconds before showing the progress bar.
    persist: Should the progress bar be cleared at the end.
    enabled: If false, disable the progress bar.
        If None, enable if output is tty.
    file: File like object to write progress bar to. stderr by default
    timer: Function to use for time.
    """
    if file is None:
        file = sys.stderr

    if enabled is None:
        enabled = file.isatty()

    if not enabled:
        # Just return the values.
        yield from iterable
        return

    count = 0
    length = len(iterable)
    iterable = iter(iterable)

    # Start returning values from iterable until
    # delay time passes.
    start = timer()
    while timer() - start < delay:
        try:
            yield next(iterable)
        except StopIteration:
            return
        else:
            count += 1

    # Start showing progress bar
    tick_start = start
    tick_duration = 1 / ticks
    progress_shown = False

    while True:
        # Show progress
        if timer() - tick_start > tick_duration:
            # Update the tick start
            tick_start = timer()

            # Clear progress up until now
            if progress_shown: file.write(clear_line())

            # Print the progress
            print_progress(count, length, timer() - start, file = file)
            progress_shown = True

        # Yield next value
        try:
            yield next(iterable)
        except StopIteration:
            break
        else:
            count += 1

    # Clear progress up until now
    if progress_shown: file.write(clear_line())

    # Print final progress
    print_progress(count, length, timer() - start, file = file)

    if persist:
        # Show progress bar permanently.
        file.write("\n")
    else:
        # Use format code to clear progress bar
        file.write(clear_line())

    file.flush()

def print_progress(count, length, duration, file = None):
    """Format progress bar"""
    if file is None:
        file = sys.stderr

    if length:
        percent = f"{count * 100 / length:.2f}%"
    else:
        percent = "-.--%"

    ratio = f"{count} / {length}"
    elapsed = duration_fmt(duration)

    if count:
        projected = duration_fmt(max(duration * (1. / count * length - 1), 0))
    else:
        projected = "-- secs"

    file.write(
        f"Progress: {percent} ({ratio}) Elapsed: {elapsed} "
        f"Remaining: {projected}\r")
    file.flush()

SECONDS_PER_MINUTE = 60.
SECONDS_PER_HOUR = 60. * 60
SECONDS_PER_DAY = 60. * 60 * 24

def duration_fmt(duration):
    """Format duration in seconds as a string."""
    parts = []

    if duration > SECONDS_PER_DAY:
        days, duration = divmod(duration, SECONDS_PER_DAY)
        parts.append(f"{days:.0f} days")

    if duration > SECONDS_PER_HOUR:
        hours, duration = divmod(duration, SECONDS_PER_HOUR)
        parts.append(f"{hours:.0f} hrs")

    if duration > SECONDS_PER_MINUTE:
        minutes, duration = divmod(duration, SECONDS_PER_MINUTE)
        parts.append(f"{minutes:.0f} mins")

    parts.append(f"{duration:.2f} secs")

    return " ".join(parts)

def wait_exception_or_completed(fs, timeout = None):
    """
    Wait for all futures to complete or one to raise an exception.
    """
    done, not_done = concurrent.futures.wait(
        fs, timeout, concurrent.futures.FIRST_EXCEPTION)

    for future in done:
        if future.exception():
            # Stop because exception was raised
            return True

    if not not_done:
        # Stop because all futures are done
        return True

    return False

class ProgressWorker:
    def __init__(self, iterable, tick_duration, lock, count_value, timer = time.perf_counter):
        """
        Show a progress bar for iterable.
        iterable: The object to return items from.
        tick_duration: Pause in seconds between each update.
        lock: Lock to use for updating count.
        count_value: Value to update with count.
        timer: Time function to use.
        """
        self.iterable = iterable
        self.tick_duration = tick_duration
        self.lock = lock
        self.count_value = count_value
        self.timer = timer

    def __iter__(self):
        """
        Loop over iterable and update progress bar.
        iterable: The object to return items from.
        """
        iterable = iter(self.iterable)

        # Start showing progress bar
        tick_start = self.timer()

        count = 0
        while True:
            # Update progress
            if self.timer() - tick_start > self.tick_duration:
                # Update the tick start
                tick_start = self.timer()

                # Update count
                with self.lock:
                    self.count_value.value += count
                count = 0

            # Yield next value
            try:
                yield next(iterable)
            except StopIteration:
                break
            else:
                count += 1

        # Send final count
        with self.lock:
            self.count_value.value += count

class ProgressBarMP:
    """
    Show a progress bar for multiprocessing.
    Meant to represent a progress bar for a number of items to be processed.
    """
    def __init__(self, length, ticks = 10, delay = 0.5,
                persist = False, enabled = None, file = None,
                timer = time.perf_counter, manager = None):
        """
        length: Number of items that will be processed.
        ticks: Maximum number of updates per second.
        delay: Delay in seconds before showing the progress bar.
        persist: Should the progress bar be cleared at the end.
        enabled: If false, disable the progress bar.
            If None, enable if output is tty.
        file: File like object to write progress bar to. stderr by default
        timer: Function to use for time.
        manager: Multiprocessing manager to create synchronization objects.
        """
        if file is None:
            file = sys.stderr

        if enabled is None:
            enabled = file.isatty()

        self.length = length
        self.tick_duration = 1 / ticks
        self.delay = delay
        self.persist = persist
        self.enabled = enabled
        self.file = file
        self.timer = timer

        # The count of completed task needs to be kept.
        # But time remaining is actually a separate operation.
        # As the time remaining is the time of the longest taking task.
        if manager is None:
            manager = Manager()

        # Use an explicit lock so shared objects share a lock
        # https://bugs.python.org/issue35786 !!!
        self.lock = manager.Lock()
        self.count_value = manager.Value("i", 0, lock = False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Close the progress bar.
        """
        if exc_type is not None:
            # Let exception propagate
            return False

        self.close()

    def worker_loop(self, iterable):
        """
        Loop over iterable and update progress bar.
        iterable: The object to return items from.
        """
        # If disabled, just return the values.
        if not self.enabled:
            return iterable

        # Otherwise create and return ProgressWorker
        return ProgressWorker(iterable, self.tick_duration, self.lock, self.count_value, self.timer)

    def parent_loop(self, wait_check):
        """
        Print progress bar and wait for completion.
        NOTE: wait_check() must return True when loop should exit
        Otherwise, a deadlock is possible is a subprocess is killed, and does not complete.
        """
        # If disabled, just exit
        if not self.enabled:
            return

        if wait_check is None:
            # NOTE: Can deadlock, you have been warned.
            wait_check = time.sleep

        # Start timing
        start = self.timer()

        # Just wait for delay period to pass.
        if wait_check(self.delay):
            return

        # Start showing progress bar
        progress_shown = False
        try:
            while True:
                # Get count, length
                count = self.count_value.value

                # Stop if complete
                if count >= self.length:
                    break

                # Clear progress line
                if progress_shown: self.file.write(clear_line())

                # Print the progress
                print_progress(count, self.length, self.timer() - start, file = self.file)
                progress_shown = True

                # Wait for next tick
                if wait_check(self.delay):
                    count = self.count_value.value
                    break
        finally:
            # Clear progress up until now
            if progress_shown: self.file.write(clear_line())

            # Print final progress
            print_progress(count, self.length, self.timer() - start, file = self.file)

            if self.persist:
                # Show progress bar permanently.
                self.file.write("\n")
            else:
                # Use format code to clear progress bar
                self.file.write(clear_line())
            self.file.flush()

    def is_finished(self):
        """
        Check if progress bar is finished.
        """
        return self.count_value.value >= self.length

    def close(self):
        """
        Close the progress bar. Verifies progress is complete."""
        if self.count_value.value != self.length:
            # Exited cleanly, but not complete
            raise RuntimeError("Progress bar finished early at "
                               f"{self.count_value.value} / {self.length}")
