"""
Utility functions to help with display progress and
time taken.
"""
import sys
import time

from functools import wraps
from multiprocessing import RLock, Value

try:
    from colorama.ansi import clear_line
except NameError:
    clear_line = lambda: None

def progress_bar(iterable, ticks = 10, delay = 0.5,
                persist = False, enabled = None, timer = time.perf_counter):
    """
    Show a simply progress bar for iterable.
    iterable: The object to return items from.
    ticks: Maximum number of updates per second.
    delay: Delay in seconds before showing the progress bar.
    persist: Should the progress bar be cleared at the end.
    enabled: If false, disable the progress bar.
        If None, enable if output is tty.
    timer: Function to use for time.
    """
    if enabled is None:
        enabled = sys.stdout.isatty()

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
            if progress_shown: print(clear_line(), end = "")

            # Print the progress
            print_progress(count, length, timer() - start)
            progress_shown = True

        # Yield next value
        try:
            yield next(iterable)
        except StopIteration:
            break
        else:
            count += 1

    # Clear progress up until now
    if progress_shown:
        print(clear_line(), end = "")

    # Print final progress
    print_progress(count, length, timer() - start)

    if persist:
        # Show progress bar permanently.
        print()
    else:
        # Use format code to clear progress bar
        print(clear_line(), end = "")

def print_progress(count, length, duration):
    """Format progress bar"""
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

    print(f"Progress: {percent} ({ratio}) Elapsed: {elapsed} "
          f"Remaining: {projected}", end = "\r")

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

class PickleGenerator:
    """
    Internal class to represent a wrapped generator.
    """
    def __init__(self, generator, *args, **kwargs):
        self.generator = generator
        self.args = args
        self.kwargs = kwargs

    def __iter__(self):
        return iter(self.generator(*self.args, **self.kwargs))

def pickleable_generator(generator):
    """
    Allow pickling of generators. While it is not possible to truly
    pickle a generator, this gets around the issue by not creating
    the generator, and just saving the arguments.
    """
    @wraps(generator)
    def wrapper(*args, **kwargs):
        #return PickleGenerator(generator, *args, **kwargs)
        return PickleGenerator(generator, *args, **kwargs)

    generator.__qualname__ += ".__wrapped__"
    return wrapper

class ProgressBarMP:
    """
    Show a progress bar for multiprocessing.
    """
    def __init__(self, ticks = 10, delay = 0.5,
                persist = False, enabled = None, timer = time.perf_counter):
        """
        ticks: Maximum number of updates per second.
        delay: Delay in seconds before showing the progress bar.
        persist: Should the progress bar be cleared at the end.
        enabled: If false, disable the progress bar.
            If None, enable if output is tty.
        timer: Function to use for time.
        """
        if enabled is None:
            enabled = sys.stdout.isatty()

        self.ticks = ticks
        self.delay = delay
        self.persist = persist
        self.enabled = enabled
        self.timer = timer

        # The count of completed task needs to be kept.
        # But time remaining is actually a separate operation.
        # As the time remaining is the time of the longest taking task.

        # Use an explicit lock so shared objects share a lock
        lock = RLock()
        self.count = Value("i", 0, lock = lock)
        self.length = Value("i", 0, lock = lock)

    @pickleable_generator
    def worker_loop(self, iterable, length = None):
        """
        Loop over iterable and update progress bar.
        iterable: The object to return items from.
        length: The length of the iterable. If None, use len().
        """
        # If disabled, just return the values.
        if not self.enabled:
            yield from iterable
            return

        if length is None:
            length = len(iterable)
        iterable = iter(iterable)

        # Set length
        with self.length.get_lock():
            self.length.value += length

        # Start showing progress bar
        tick_start = self.timer()
        tick_duration = 1 / self.ticks

        count = 0
        while True:
            # Show progress
            if self.timer() - tick_start > tick_duration:
                # Update the tick start
                tick_start = self.timer()

                # Update count
                with self.count.get_lock():
                    self.count.value += count
                count = 0

            # Yield next value
            try:
                yield next(iterable)
            except StopIteration:
                break
            else:
                count += 1

        # Send final count
        with self.count.get_lock():
            self.count.value += count

    def parent_loop(self):
        """
        Print progress bar and wait for completion.
        """
        # If disabled, just exit
        if not self.enabled:
            return

        # Just wait for delay period to pass.
        time.sleep(self.delay)

        # Start showing progress bar
        start = self.timer()
        tick_duration = 1 / self.ticks
        progress_shown = False

        while True:
            # Get count, length
            count = self.count.value
            length = self.length.value

            # Stop if complete
            if count == length:
                break

            # Clear progress line
            if progress_shown: print(clear_line(), end = "")

            # Print the progress
            print_progress(count, length, self.timer() - start)
            progress_shown = True

            # Wait for next tick
            time.sleep(tick_duration)

        # Clear progress up until now
        if progress_shown: print(clear_line(), end = "")

        # Print final progress
        print_progress(count, length, self.timer() - start)

        if self.persist:
            # Show progress bar permanently.
            print()
        else:
            # Use format code to clear progress bar
            print(clear_line(), end = "")
