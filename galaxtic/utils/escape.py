def escape_markdown(text: str) -> str:
    """
    Escape text from rendering as markdown in the given text.
    
    Args:
        text (str): The input text to escape.
    Returns:
        str: The escaped text with markdown special characters replaced.
    """
    escape_chars = r'\`*_{}[]()#+-.!'
    for char in escape_chars:
        text = text.replace(char, fr'\{char}')
    return text