import time
import functools

def timer(label: str = None):
    """
    Décorateur pour mesurer le temps d'exécution d'une fonction.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = label or func.__name__
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            print(f"⏱️ {name} : {duration:.2f} s")
            return result
        return wrapper
    return decorator
