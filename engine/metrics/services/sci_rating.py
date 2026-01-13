def compute_rating_from_sci(sci_score: float) -> str:
    if sci_score <= 1.2:
        return "A+"
    if sci_score <= 1.5:
        return "A"
    if sci_score <= 2.0:
        return "B"
    if sci_score <= 3.0:
        return "C"
    return "E"
