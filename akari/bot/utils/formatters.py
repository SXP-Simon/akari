def format_code_block(content: str, language: str = "") -> str:
    """
    格式化代码块。
    Args:
        content (str): 代码内容。
        language (str): 代码语言。
    Returns:
        str: 格式化后的代码块字符串。
    """
    return f"```{language}\n{content}\n```"
 
def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    截断文本，避免超过Discord限制。
    Args:
        text (str): 原始文本。
        max_length (int): 最大长度。
    Returns:
        str: 截断后的文本。
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."