import itertools

def batched(iterable, n):
    """
    Batch data into iterators of length n. The last batch may be shorter.
    This is a polyfill for itertools.batched() in Python 3.12+
    """
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while True:
        chunk_it = itertools.islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield itertools.chain((first_el,), chunk_it)

def bitmask_to_list(intflag):
    n = type(intflag).__name__
    if not str(intflag).startswith(n):
        return []
    return str(intflag)[len(n)+1:].split('|')