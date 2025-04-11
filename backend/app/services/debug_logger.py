from colorama import Fore, Style, init

# Initialize colorama for Windows compatibility
init(autoreset=True)

def log_debug(message: str):
    """
    Logs a debug message in cyan color for visibility.

    Args:
        message (str): The debug message to print.
    """
    print(f"{Fore.CYAN}[DEBUG] {message}{Style.RESET_ALL}")
