import os
import sys
import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

BANNER = """
 █   █  ███   ████ █   █       ███  █     ███ 
██ ██ █   █ █     █  █       █     █      █  
█ █ █ █████  ███  ███   ████ █     █      █  
█   █ █   █     █ █  █       █     █      █  
█   █ █   █ ████  █   █       ███  █████ ███
"""

def check_connectivity():
    try:
        r1 = requests.head("https://api.guerrillamail.com/ajax.php", timeout=2)
        if r1.status_code < 400:
            return "[bold #6699cc][Online][/bold #6699cc]"
    except:
        pass
    return "[dim][Offline][/dim]"

def print_branded_banner():
    status = check_connectivity()
    banner_panel = Panel(
        BANNER.strip(),
        style="#6699cc on #1c1c1c",
        border_style="bright_black",
        expand=False,
        padding=(1, 4),
        title=f"{status}",
        title_align="right"
    )
    console.print(banner_panel)

def print_footer():
    footer_text = "[dim][1-2] Select Manager | [q] Exit Mask-CLI[/dim]"
    console.print(f"\n{footer_text}")

def main():
    while True:
        console.clear()
        print_branded_banner()
        # Tagline: Instant privacy through temporary accounts.
        console.print(f"\n[bold white]  Instant privacy through temporary accounts.[/bold white]")
        console.print("[dim]  ───────────────────────────────────────────[/dim]\n")

        console.print("  [white]1[/white] : Email Manager")
        console.print("  [white]2[/white] : SMS Manager")
        
        print_footer()

        choice = input("\n> ").strip().lower()
        if choice == "1":
            os.system("python mask_mail.py")
        elif choice == "2":
            os.system("python mask_sms.py")
        elif choice in ("q", "b"):
            break

if __name__ == "__main__":
    main()
