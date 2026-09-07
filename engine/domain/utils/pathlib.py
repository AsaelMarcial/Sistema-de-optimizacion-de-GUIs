from pathlib import Path

def find_by_exact_name(part: str, base_path: str = ".") -> list:
    """
    Finds files or directories by their exact name using pathlib.
    
    :param part: The partial path or exact name to search for.
    :param base_path: The root directory where the search starts (defaults to current directory).
    :return: A list of Path objects relative to the base path.
    """
    path = Path(part)
    base = Path(base_path)
    results = []
    
    # Check if the provided path is an existing file
    if path.is_file():
        # rglob searches recursively for the exact file name
        for found in base.rglob(path.name):
            if found.is_file():
                # Store the path relative to the base directory
                results.append(found.relative_to(base))
                
    # Check if the provided path is an existing directory or has no file extension
    elif path.is_dir() or not path.suffix:
        # rglob searches recursively for the exact directory name
        for found in base.rglob(path.name):
            if found.is_dir():
                # Store the path relative to the base directory
                results.append(found.relative_to(base))
                
    return results

