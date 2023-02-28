"""
Utility functions to help with display progress and
time taken.
"""
import sys
import time

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
            print_progress(count, length, start, timer())
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
    print_progress(count, length, start, timer())

    if persist:
        # Show progress bar permanently.
        print()
    else:
        # Use format code to clear progress bar
        print(clear_line(), end = "")

def print_progress(count, length, start, stop):
    """Format progress bar"""
    percent = f"{count * 100 / length:.2f}%"
    ratio = f"{count} / {length}"
    elapsed = duration_fmt(stop - start)
    projected = max((stop - start) * (1. / count * length - 1), 0)
    projected = duration_fmt(projected)

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
        parts.append(f"{hours:.0f} hr")

    if duration > SECONDS_PER_MINUTE:
        minutes, duration = divmod(duration, SECONDS_PER_MINUTE)
        parts.append(f"{minutes:.0f} min")

    parts.append(f"{duration:.2f} sec")

    return " ".join(parts)
