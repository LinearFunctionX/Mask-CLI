import json
import os
import requests
import sys
import argparse
import threading
import time
import msvcrt
import pyperclip
import re
from bs4 import BeautifulSoup
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.align import Align

# SMS Online Provider
BASE_URL = "https://sms-online.co"
HOME_DIR = os.path.expanduser("~")
STORAGE_FILE = os.path.join(HOME_DIR, ".mask_numbers.json")
CONFIG_FILE = os.path.join(HOME_DIR, ".mask_config.json")

console = Console()

BANNER_STR = """
 █   █  ███   ████ █   █       ███  █     ███ 
██ ██ █   █ █     █  █       █     █      █  
█ █ █ █████  ███  ███   ████ █     █      █  
█   █ █   █     █ █  █       █     █      █  
█   █ █   █ ████  █   █       ███  █████ ███
"""

def check_connectivity():
    try:
        r = requests.head(BASE_URL, timeout=2)
        if r.status_code < 400:
            return "[bold #6699cc][Online][/bold #6699cc]"
    except: pass
    return "[dim][Offline][/dim]"

def get_branded_banner():
    status = check_connectivity()
    return Panel(
        BANNER_STR.strip(),
        style="#6699cc on #1c1c1c",
        border_style="bright_black",
        expand=False,
        padding=(1, 4),
        title=f"{status}",
        title_align="right"
    )

def print_branded_banner():
    console.print(get_branded_banner())

def print_footer(mode="menu"):
    if mode == "menu":
        text = "[dim][p] Pick | [0-9] Open | [w] Webhook | [b] Back[/dim]"
    elif mode == "sub":
        text = "[dim][v] View | [d] Delete | [b] Back[/dim]"
    else: # inbox
        text = "[dim][↑↓] Navigate | [ENTER] View | [white]/[/white] Search | [e] Export | [b] Back[/dim]"
    console.print(f"\n{text}")

def interactive_confirm(prompt_text):
    selected = False # False = No, True = Yes
    with Live(auto_refresh=False) as live:
        while True:
            yes_style = "bold white on #6699cc" if selected else "white"
            no_style = "bold white on #6699cc" if not selected else "white"
            
            content = Panel(
                Align.center(
                    f"[white]{prompt_text}[/white]\n\n"
                    f"[{yes_style}]   YES   [/{yes_style}]      [{no_style}]   NO    [/{no_style}]"
                ),
                border_style="bright_black",
                padding=(1, 4),
                expand=False,
                style="on black"
            )
            live.update(Align.center(content), refresh=True)
            
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\xe0', b'\x00'):
                    ch2 = msvcrt.getch()
                    if ch2 in (b'K', b'M'): # Left or Right
                        selected = not selected
                elif ch == b'\r':
                    return selected
                elif ch.lower() == b'n': return False
                elif ch.lower() == b'y': return True
                elif ch.lower() == b'b': return False
            time.sleep(0.05)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class SMSAPI:
    @staticmethod
    def get_available_numbers():
        try:
            url = f"{BASE_URL}/receive-free-sms"
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                numbers = []
                for a in soup.select('a[href*="/receive-free-sms/"]'):
                    num_text = a.text.strip()
                    href = a['href']
                    raw_num = href.split('/')[-1]
                    if raw_num.isdigit():
                        numbers.append({"display": num_text, "raw": raw_num, "url": href, "seen_count": 0})
                return numbers
        except: pass
        return []

    @staticmethod
    def get_messages(number_url):
        try:
            response = requests.get(number_url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                messages = []
                for item in soup.select('.list-item'):
                    spans = item.find_all('span')
                    if len(spans) >= 2:
                        sender = spans[0].text.strip()
                        time_ago = spans[1].text.strip()
                        text = item.text.replace(sender, "").replace(time_ago, "").strip()
                        messages.append({"from": sender, "time": time_ago, "text": text})
                return messages
        except: pass
        return None

class Storage:
    @staticmethod
    def load_numbers():
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r") as f:
                    return json.load(f)
            except: return []
        return []

    @staticmethod
    def save_numbers(numbers):
        with open(STORAGE_FILE, "w") as f:
            json.dump(numbers, f)

    @staticmethod
    def get_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except: pass
        return {"webhook_url": ""}

    @staticmethod
    def save_config(config):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

def send_webhook(msg_data, phone_num):
    config = Storage.get_config()
    url = config.get("webhook_url")
    if not url: return
    
    # Enhanced, clearer payload structure
    payload = {
        "embeds": [{
            "title": "New SMS Received",
            "color": 6737084, # #6699cc
            "fields": [
                {"name": "To Number", "value": f"`{phone_num}`", "inline": True},
                {"name": "From", "value": f"`{msg_data['from']}`", "inline": True},
                {"name": "Message", "value": msg_data['text']}
            ],
            "footer": {"text": "Mask-CLI | Automatic SMS Forwarder"}
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code >= 400:
            console.print(f"[red]Webhook error ({response.status_code})[/red]")
    except Exception as e:
        console.print(f"[red]Webhook connection failed: {e}[/red]")

class InboxRenderable:
    def __init__(self, number_display, messages, selected_idx, filter_str="", initial_texts=None):
        self.number_display = number_display
        self.messages = messages
        self.selected_idx = selected_idx
        self.filter_str = filter_str
        self.initial_texts = initial_texts or set()

    def __rich__(self):
        banner = get_branded_banner()
        table = Table(box=None, header_style="bold white", padding=(0, 2), show_edge=False)
        table.add_column("", width=2)
        table.add_column("FROM", style="white")
        table.add_column("TIME", style="bright_black")
        table.add_column("CONTENT", style="white")
        
        filtered = self.messages
        if self.filter_str:
            f = self.filter_str.lower()
            filtered = [m for m in self.messages if f in m['text'].lower() or f in m['from'].lower()]

        if not filtered:
            table.add_row("", "[dim]Waiting for SMS...[/dim]" if not self.filter_str else "[dim]No match...[/dim]", "", "")
        else:
            for i, msg in enumerate(filtered):
                is_new = msg['text'] not in self.initial_texts
                sel = "[bold white]>[/bold white]" if i == self.selected_idx else " "
                
                content = msg['text']
                from_addr = msg['from']
                
                if self.filter_str:
                    pattern = re.compile(re.escape(self.filter_str), re.IGNORECASE)
                    content = pattern.sub(lambda m: f"[bold #6699cc]{m.group(0)}[/bold #6699cc]", content)
                    from_addr = pattern.sub(lambda m: f"[bold #6699cc]{m.group(0)}[/bold #6699cc]", from_addr)

                style = "bold #6699cc" if is_new else ("bold white" if i == self.selected_idx else "white")
                marker = "[bold #6699cc]NEW[/bold #6699cc] " if is_new else ""
                
                if len(content) > 50: content = content[:47] + "..."
                table.add_row(sel, from_addr, msg['time'], f"{marker}[{style}]{content}[/{style}]")
        
        panel = Panel(
            table, 
            title=f" [bold white]Mask-CLI | SMS:[/bold white] {self.number_display} ", 
            title_align="left",
            border_style="bright_black",
            expand=False
        )
        return Group(banner, "\n", panel)

def view_loop(account, wait_keyword=None):
    pyperclip.copy(account['raw'])
    console.print(f"[dim]Synced and copied to clipboard: {account['raw']}[/dim]")

    initial_msgs = SMSAPI.get_messages(account['url'])
    initial_texts = {m['text'] for m in initial_msgs} if initial_msgs else set()

    shared_data = {
        'messages': initial_msgs or [], 
        'stop': False, 
        'selected_idx': 0, 
        'filter': "",
        'last_seen_text': initial_msgs[0]['text'] if initial_msgs else None,
        'initial_texts': initial_texts
    }
    
    def fetcher():
        while not shared_data['stop']:
            new_msgs = SMSAPI.get_messages(account['url'])
            if new_msgs is not None:
                if shared_data['messages'] and not new_msgs:
                    time.sleep(5); continue
                if new_msgs:
                    top_msg = new_msgs[0]
                    if shared_data['last_seen_text'] and top_msg['text'] != shared_data['last_seen_text']:
                        send_webhook(top_msg, account['display'])
                        if wait_keyword and wait_keyword.lower() in top_msg['text'].lower():
                            shared_data['found_msg'] = top_msg
                            shared_data['stop'] = True; break
                    shared_data['last_seen_text'] = top_msg['text']
                shared_data['messages'] = new_msgs
            time.sleep(15)

    if wait_keyword:
        console.print(f"[dim]Waiting silently for keyword: '{wait_keyword}' on {account['display']}...[/dim]")
        fetcher_thread = threading.Thread(target=fetcher, daemon=True)
        fetcher_thread.start()
        while not shared_data['stop']: time.sleep(1)
        msg = shared_data['found_msg']
        console.print("\n[bold green]MATCH FOUND![/bold green]")
        console.print(f"[bold white]From:[/bold white] {msg['from']}")
        console.print(msg['text'])
        return

    t = threading.Thread(target=fetcher, daemon=True)
    t.start()

    console.clear()
    try:
        with Live(InboxRenderable(account['display'], shared_data['messages'], 0, "", initial_texts), console=console, refresh_per_second=2) as live:
            while True:
                live.update(InboxRenderable(account['display'], shared_data['messages'], shared_data['selected_idx'], shared_data['filter'], initial_texts))
                print_footer("inbox")
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'\xe0', b'\x00'):
                        ch2 = msvcrt.getch()
                        if ch2 == b'H': shared_data['selected_idx'] = max(0, shared_data['selected_idx'] - 1)
                        elif ch2 == b'P': 
                            filtered = [m for m in shared_data['messages'] if shared_data['filter'].lower() in m['text'].lower() or shared_data['filter'].lower() in m['from'].lower()] if shared_data['filter'] else shared_data['messages']
                            shared_data['selected_idx'] = min(len(filtered) - 1, shared_data['selected_idx'] + 1)
                    
                    elif ch == b'/':
                        live.stop()
                        search_panel = Panel("[bold white]SEARCH SMS[/bold white]\n[dim]Enter keyword to filter your inbox...[/dim]", border_style="#6699cc", padding=(1, 2), title="[bold white]FILTER[/bold white]")
                        console.print(search_panel)
                        shared_data['filter'] = input("> ").strip()
                        shared_data['selected_idx'] = 0
                        console.clear(); live.start()
                    elif ch.lower() == b'c':
                        shared_data['filter'] = ""; shared_data['selected_idx'] = 0; console.clear()
                    elif ch.lower() == b'e': # EXPORT
                        filtered = [m for m in shared_data['messages'] if shared_data['filter'].lower() in m['text'].lower() or shared_data['filter'].lower() in m['from'].lower()] if shared_data['filter'] else shared_data['messages']
                        if filtered:
                            msg = filtered[shared_data['selected_idx']]
                            filename = f"mask_sms_{int(time.time())}.txt"
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(f"From: {msg['from']}\nTime: {msg['time']}\n\n{msg['text']}")
                            live.stop(); console.print(f"[green]Exported to {filename}[/green]"); time.sleep(1); live.start()
                    elif ch == b'\r':
                        filtered = [m for m in shared_data['messages'] if shared_data['filter'].lower() in m['text'].lower() or shared_data['filter'].lower() in m['from'].lower()] if shared_data['filter'] else shared_data['messages']
                        if filtered:
                            msg = filtered[shared_data['selected_idx']]
                            live.stop(); console.clear(); print_branded_banner()
                            console.print("\n" + "─" * 60, style="bright_black")
                            console.print(f"[bold white]From:[/bold white] {msg['from']}\n[bold white]Time:[/bold white] {msg['time']}\n" + "─" * 60, style="bright_black")
                            console.print(msg['text'], style="white")
                            console.print("\n" + "─" * 60 + "\n", style="bright_black")
                            console.print("[dim]Press any key to return...[/dim]")
                            msvcrt.getch(); console.clear(); live.start()
                    elif ch.lower() == b'b':
                        numbers = Storage.load_numbers()
                        for n in numbers:
                            if n['raw'] == account['raw']:
                                n['seen_count'] = len(shared_data['messages']); break
                        Storage.save_numbers(numbers); console.clear(); break
                time.sleep(0.05)
    finally: shared_data['stop'] = True

def interactive_confirm(prompt_text):
    selected = False # False = No, True = Yes
    with Live(auto_refresh=False) as live:
        while True:
            yes_style = "bold white on #6699cc" if selected else "white"
            no_style = "bold white on #6699cc" if not selected else "white"
            
            content = Panel(
                Align.center(
                    f"[white]{prompt_text}[/white]\n\n"
                    f"[{yes_style}]   YES   [/{yes_style}]      [{no_style}]   NO    [/{no_style}]"
                ),
                border_style="bright_black",
                padding=(1, 4),
                expand=False,
                style="on black"
            )
            live.update(Align.center(content), refresh=True)
            
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\xe0', b'\x00'):
                    ch2 = msvcrt.getch()
                    if ch2 in (b'K', b'M'): # Left or Right
                        selected = not selected
                elif ch == b'\r':
                    return selected
                elif ch.lower() == b'n': return False
                elif ch.lower() == b'y': return True
                elif ch.lower() == b'b': return False
            time.sleep(0.05)

def main_menu():
    while True:
        console.clear(); print_branded_banner()
        saved_numbers = Storage.load_numbers()
        console.print(f"\n[bold white]  Instant privacy through temporary accounts. | SMS[/bold white]")
        console.print("[dim]  ─────────────────────────────────────────────────────────[/dim]\n")
        console.print("  [white]p[/white] : [bold white]Pick New Number from Public List[/bold white] [dim]- Browse international numbers.[/dim]")
        for i, n in enumerate(saved_numbers):
            try:
                msgs = SMSAPI.get_messages(n['url'])
                curr_count = len(msgs) if msgs is not None else 0
                seen = n.get('seen_count', 0)
                diff = curr_count - seen
                badge = f" [bold #6699cc]({diff} new)[/bold #6699cc]" if diff > 0 else ""
                console.print(f"  [white]{i}[/white] : {n['display']}{badge}")
            except: console.print(f"  [white]{i}[/white] : {n['display']}")
        console.print("  [white]w[/white] : [bold white]Set/Reset Webhook URL[/bold white] [dim]- Forward new SMS to Discord/Slack.[/dim]")
        console.print("  [white]b[/white] : [bold white]Back to Main Menu[/bold white]                [dim]- Return to the suite selector.[/dim]")
        print_footer("menu")
        try: choice = input("\n> ").strip().lower()
        except EOFError: break
        
        if choice == 'b': break
        elif choice == 'w':
            curr = Storage.get_config().get("webhook_url", "")
            if curr:
                if interactive_confirm(f"Reset current webhook?"):
                    Storage.save_config({"webhook_url": ""}); console.print("[green]Webhook reset.[/green]")
                else: continue
            url = input("Enter Discord/Slack Webhook URL [b for back]: ").strip()
            if not url or url.lower() == 'b': continue
            if interactive_confirm(f"Forward to {url}?"):
                Storage.save_config({"webhook_url": url}); console.print("[green]Saved.[/green]")
        elif choice == 'p':
            while True:
                available = SMSAPI.get_available_numbers()
                if not available: console.print("[red]Failed.[/red]"); break
                console.clear(); print_branded_banner()
                console.print("\n[bold white]AVAILABLE NUMBERS:[/bold white]")
                for i, n in enumerate(available): console.print(f"  [white]{i}[/white] : {n['display']}")
                console.print("  [white]b[/white] : Back")
                pick = input("\nPick a number: ").strip().lower()
                if pick == 'b': break
                if pick.isdigit():
                    idx = int(pick)
                    if 0 <= idx < len(available):
                        selected = available[idx]
                        if not any(s['raw'] == selected['raw'] for s in saved_numbers):
                            saved_numbers.append(selected); Storage.save_numbers(saved_numbers)
                        view_loop(selected)
        elif choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(saved_numbers):
                acc = saved_numbers[idx]
                while True:
                    console.clear(); print_branded_banner()
                    console.print(f"\n[dim]Selected: {acc['display']}[/dim]")
                    console.print("  [white]v[/white] : View Inbox\n  [white]d[/white] : Delete Number\n  [white]b[/white] : Back")
                    print_footer("sub")
                    sub = input("\n> ").strip().lower()
                    if sub == 'v': view_loop(acc); break
                    elif sub == 'd':
                        if interactive_confirm(f"Delete {acc['display']}?"):
                            saved_numbers.pop(idx); Storage.save_numbers(saved_numbers); break
                    elif sub == 'b': break

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--pick", action="store_true")
    parser.add_argument("--wait", help="Silent mode")
    args = parser.parse_args()
    if args.wait:
        available = SMSAPI.get_available_numbers()
        if available:
            console.print("\n[bold white]AVAILABLE NUMBERS:[/bold white]")
            for i, n in enumerate(available): console.print(f"  [white]{i}[/white] : {n['display']}")
            pick = input("\nPick a number to wait on: ").strip()
            if pick.isdigit():
                idx = int(pick)
                if 0 <= idx < len(available): view_loop(available[idx], wait_keyword=args.wait)
        sys.exit()
    if args.pick:
        available = SMSAPI.get_available_numbers()
        if available:
            console.print("\n[bold white]AVAILABLE NUMBERS:[/bold white]")
            for i, n in enumerate(available): console.print(f"  [white]{i}[/white] : {n['display']}")
            pick = input("\nPick a number: ").strip()
            if pick.isdigit():
                idx = int(pick)
                if 0 <= idx < len(available): view_loop(available[idx])
        sys.exit()
    main_menu()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(0)
