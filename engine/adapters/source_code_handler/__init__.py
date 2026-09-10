def apply_tokens_to_project(*args, **kwargs):
    from .code_processor import apply_tokens_to_project as function

    return function(*args, **kwargs)


def evaluate_and_apply_heuristics(*args, **kwargs):
    from .code_processor import evaluate_and_apply_heuristics as function

    return function(*args, **kwargs)


def load_transformed_html(*args, **kwargs):
    from .code_processor import load_transformed_html as function

    return function(*args, **kwargs)

__all__ = [
    "apply_tokens_to_project",
    "evaluate_and_apply_heuristics",
    "load_transformed_html",
]
