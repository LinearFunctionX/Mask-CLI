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

# Guerrilla Mail API Base
BASE_URL = "https://api.guerrillamail.com/ajax.php"
HOME_DIR = os.path.expanduser("~")
STORAGE_FILE = os.path.join(HOME_DIR, ".mask_mails.json")
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
    except:
        pass
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
        text = "[dim][n] New | [0-9] Open | [w] Webhook | [b] Back[/dim]"
    else: # inbox
        text = "[dim][↑↓] Navigate | [ENTER] View | [white]/[/white] Search | [e] Export | [b] Back[/dim]"
    console.print(f"\n{text}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class TempMailAPI:
    @staticmethod
    def generate_email():
        try:
            response = requests.get(f"{BASE_URL}?f=get_email_address", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {"email": data['email_addr'], "sid": data['sid_token'], "timestamp": time.time(), "seen_count": 0}
        except: pass
        return None

    @staticmethod
    def set_session(email):
        try:
            user, domain = email.split("@")
            response = requests.get(f"{BASE_URL}?f=set_email_user&email_user={user}&domain={domain}", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.json().get('sid_token')
        except: pass
        return None

    @staticmethod
    def get_messages(sid):
        try:
            response = requests.get(f"{BASE_URL}?f=get_email_list&offset=0&sid_token={sid}", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                return res_data.get('list', []), res_data.get('count', 0)
        except: pass
        return None, 0

    @staticmethod
    def read_message(sid, msg_id):
        try:
            response = requests.get(f"{BASE_URL}?f=fetch_email&email_id={msg_id}&sid_token={sid}", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.json()
        except: pass
        return None

class Storage:
    @staticmethod
    def load_accounts():
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r") as f:
                    return json.load(f)
            except: return []
        return []

    @staticmethod
    def save_accounts(accounts):
        with open(STORAGE_FILE, "w") as f:
            json.dump(accounts, f)

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

def send_webhook(msg_data, email_addr):
    config = Storage.get_config()
    url = config.get("webhook_url")
    if not url: return

    payload = {        "content": f"**[Mask-CLI] New Email Received!**\n**To:** `{email_addr}`\n**From:** `{msg_data['mail_from']}`\n**Subject:** `{msg_data['mail_subject']}`"
    }
    try: requests.post(url, json=payload, timeout=5)
    except: pass

class InboxRenderable:
    def __init__(self, email, shared_data, selected_idx, filter_str=""):
        self.email = email
        self.shared_data = shared_data
        self.selected_idx = selected_idx
        self.filter_str = filter_str

    def __rich__(self):
        banner = get_branded_banner()
        table = Table(box=None, header_style="bold white", padding=(0, 2), show_edge=False)
        table.add_column("", width=2)
        table.add_column("ID", style="bright_black")
        table.add_column("FROM", style="white")
        table.add_column("SUBJECT", style="white")

        msgs = self.shared_data['messages']
        filtered = msgs
        if self.filter_str:
            f = self.filter_str.lower()
            filtered = [m for m in msgs if f in m['mail_subject'].lower() or f in m['mail_from'].lower()]

        if not filtered:
            table.add_row("", "", "[dim]No messages match filter...[/dim]" if self.filter_str else "[dim]Waiting for mail...[/dim]", "")
        else:
            for i, msg in enumerate(filtered):
                is_new = msg['mail_id'] not in self.shared_data['initial_ids']
                sel = "[bold white]>[/bold white]" if i == self.selected_idx else " "

                # Style and Highlight
                subject = msg['mail_subject']
                from_addr = msg['mail_from']

                if self.filter_str:
                    # Highlight matching text
                    pattern = re.compile(re.escape(self.filter_str), re.IGNORECASE)
                    subject = pattern.sub(lambda m: f"[bold #6699cc]{m.group(0)}[/bold #6699cc]", subject)
                    from_addr = pattern.sub(lambda m: f"[bold #6699cc]{m.group(0)}[/bold #6699cc]", from_addr)

                style = "bold #6699cc" if is_new else ("bold white" if i == self.selected_idx else "white")
                marker = "[bold #6699cc]NEW[/bold #6699cc] " if is_new else ""

                table.add_row(sel, str(msg['mail_id']), from_addr, f"{marker}[{style}]{subject}[/{style}]")

        elapsed = time.time() - self.shared_data.get('start_time', time.time())
        remaining = max(0, 3600 - int(elapsed))
        mins, secs = divmod(remaining, 60)

        panel = Panel(
            table,
            title=f" [bold white]Mask-CLI | MAIL:[/bold white] {self.email} ",
            title_align="left",
            border_style="bright_black",
            expand=False,
            subtitle=f" [dim]Expires: {mins:02d}:{secs:02d}[/dim] "
        )

        f_text = "[dim][↑↓] Navigate | [ENTER] View | [white]/[/white] Search | [e] Export | [b] Back[/dim]"
        if self.filter_str:
            f_text = f"[bold white]FILTER: {self.filter_str}[/bold white] | [dim][↑↓] Navigate | [ENTER] View | [c] Clear | [e] Export | [b] Back[/dim]"

        return Group(banner, "\n", panel, f"\n{f_text}")

def view_loop(account, wait_keyword=None):
    pyperclip.copy(account['email'])
    console.print(f"[dim]Synced and copied to clipboard: {account['email']}[/dim]")

    fresh_sid = TempMailAPI.set_session(account['email'])
    if fresh_sid: account['sid'] = fresh_sid

    initial_msgs, _ = TempMailAPI.get_messages(account['sid'])
    initial_ids = {m['mail_id'] for m in initial_msgs} if initial_msgs else set()

    shared_data = {
        'messages': initial_msgs or [],
        'stop': False,
        'selected_idx': 0,
        'start_time': account.get('timestamp', time.time()),
        'last_seen_id': initial_msgs[0]['mail_id'] if initial_msgs else None,
        'filter': "",
        'initial_ids': initial_ids
    }

    def fetcher():
        while not shared_data['stop']:
            new_msgs, _ = TempMailAPI.get_messages(account['sid'])
            if new_msgs is not None:
                # Disappearing messages prevention
                if shared_data['messages'] and not new_msgs:
                    time.sleep(5); continue

                if new_msgs:
                    top_id = new_msgs[0]['mail_id']
                    if shared_data['last_seen_id'] and top_id != shared_data['last_seen_id']:
                        send_webhook(new_msgs[0], account['email'])
                        if wait_keyword:
                            full_msg = TempMailAPI.read_message(account['sid'], top_id)
                            if full_msg:
                                soup = BeautifulSoup(full_msg.get('mail_body', ''), "html.parser")
                                if wait_keyword.lower() in soup.get_text().lower():
                                    shared_data['found_msg'] = full_msg
                                    shared_data['stop'] = True; break
                    shared_data['last_seen_id'] = top_id
                shared_data['messages'] = new_msgs
            time.sleep(10)

    if wait_keyword:
        console.print(f"[dim]Waiting silently for keyword: '{wait_keyword}'...[/dim]")
        fetcher_thread = threading.Thread(target=fetcher, daemon=True)
        fetcher_thread.start()
        while not shared_data['stop']: time.sleep(1)
        msg = shared_data['found_msg']
        console.print("\n[bold green]MATCH FOUND![/bold green]")
        soup = BeautifulSoup(msg.get('mail_body', ''), "html.parser")
        console.print(soup.get_text(separator="\n").strip())
        return

    t = threading.Thread(target=fetcher, daemon=True)
    t.start()

    console.clear()
    try:
        with Live(InboxRenderable(account['email'], shared_data, 0, ""), console=console, refresh_per_second=2) as live:
            while True:
                live.update(InboxRenderable(account['email'], shared_data, shared_data['selected_idx'], shared_data['filter']))
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'\xe0', b'\x00'):
                        ch2 = msvcrt.getch()
                        if ch2 == b'H': shared_data['selected_idx'] = max(0, shared_data['selected_idx'] - 1)
                        elif ch2 == b'P':
                            filtered = [m for m in shared_data['messages'] if shared_data['filter'].lower() in m['mail_subject'].lower() or shared_data['filter'].lower() in m['mail_from'].lower()] if shared_data['filter'] else shared_data['messages']
                            shared_data['selected_idx'] = min(len(filtered) - 1, shared_data['selected_idx'] + 1)
                    elif ch == b'/':
                        live.stop()
                        search_panel = Panel("[bold white]FILTER:[/bold white] ", border_style="#6699cc", padding=(0, 2))
                        console.print(search_panel)
                        shared_data['filter'] = input("> ").strip()
                        shared_data['selected_idx'] = 0
                        console.clear(); live.start()
                    elif ch.lower() == b'c':
                        shared_data['filter'] = ""; shared_data['selected_idx'] = 0; console.clear()
                    elif ch == b'\r':
                        filtered = [m for m in shared_data['messages'] if shared_data['filter'].lower() in m['mail_subject'].lower() or shared_data['filter'].lower() in m['mail_from'].lower()] if shared_data['filter'] else shared_data['messages']
                        if filtered:
                            msg_info = filtered[shared_data['selected_idx']]
                            msg = TempMailAPI.read_message(account['sid'], msg_info['mail_id'])
                            if msg:
                                live.stop(); console.clear(); print_branded_banner()
                                console.print("\n" + "─" * 60, style="bright_black")
                                console.print(f"[bold white]From:[/bold white] {msg['mail_from']}\n[bold white]Subj:[/bold white] {msg['mail_subject']}\n" + "─" * 60, style="bright_black")
                                soup = BeautifulSoup(msg.get('mail_body', ''), "html.parser")
                                console.print(soup.get_text(separator="\n").strip(), style="white")
                                console.print("\n" + "─" * 60 + "\n", style="bright_black")
                                console.print("[dim]Press any key to return...[/dim]")
                                msvcrt.getch(); console.clear(); live.start()
                    elif ch.lower() == b'e': # EXPORT
                        filtered = [m for m in shared_data['messages'] if shared_data['filter'].lower() in m['mail_subject'].lower() or shared_data['filter'].lower() in m['mail_from'].lower()] if shared_data['filter'] else shared_data['messages']
                        if filtered:
                            msg_info = filtered[shared_data['selected_idx']]
                            msg = TempMailAPI.read_message(account['sid'], msg_info['mail_id'])
                            if msg:
                                filename = f"mask_mail_{msg_info['mail_id']}.txt"
                                with open(filename, "w", encoding="utf-8") as f:
                                    f.write(f"From: {msg['mail_from']}\nSubject: {msg['mail_subject']}\n\n")
                                    soup = BeautifulSoup(msg.get('mail_body', ''), "html.parser")
                                    f.write(soup.get_text(separator="\n"))
                                live.stop(); console.print(f"[green]Exported to {filename}[/green]"); time.sleep(1); live.start()
                    elif ch.lower() == b'b':
                        accounts = Storage.load_accounts()
                        for acc in accounts:
                            if acc['email'] == account['email']:
                                acc['seen_count'] = len(shared_data['messages']); break
                        Storage.save_accounts(accounts); console.clear(); break
                time.sleep(0.05)
    finally: shared_data['stop'] = True

def interactive_confirm(prompt_text):
    selected = False # False = No, True = Yes
    with Live(auto_refresh=False) as live:
        while True:
            yes_style = "bold white on #6699cc" if selected else "white"
            no_style = "bold white on #6699cc" if not selected else "white"
            
            # Simple gray box
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

def mail_menu():
    while True:
        console.clear(); print_branded_banner()
        accounts = Storage.load_accounts()
        console.print(f"\n[bold white]  Instant privacy through temporary accounts. | MAIL[/bold white]")
        console.print("[dim]  ──────────────────────────────────────────────────────────[/dim]\n")
        console.print("  [white]n[/white] : [bold white]Generate New Email[/bold white] [dim]- Create a fresh temporary mailbox.[/dim]")
        for i, acc in enumerate(accounts):
            try:
                # Expiry check (1 hour)
                is_expired = (time.time() - acc.get('timestamp', 0)) > 3600
                expired_badge = " [bold red][EXPIRED][/bold red]" if is_expired else ""

                if not acc.get('sid'): acc['sid'] = TempMailAPI.set_session(acc['email'])
                msgs, _ = TempMailAPI.get_messages(acc['sid'])
                curr_count = len(msgs) if msgs is not None else 0
                seen = acc.get('seen_count', 0)
                diff = curr_count - seen
                badge = f" [bold #6699cc]({diff} new)[/bold #6699cc]" if (diff > 0 and not is_expired) else ""
                console.print(f"  [white]{i}[/white] : {acc['email']}{expired_badge}{badge}")
            except: console.print(f"  [white]{i}[/white] : {acc['email']}")

        console.print("  [white]w[/white] : [bold white]Set Webhook URL[/bold white]     [dim]- Forward new arrivals to Discord/Slack.[/dim]")
        console.print("  [white]b[/white] : [bold white]Back to Main Menu[/bold white]   [dim]- Return to the suite selector.[/dim]")
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
            url = input(f"Enter Discord/Slack Webhook URL [b for back]: ").strip()
            if url.lower() == 'b' or not url: continue
            Storage.save_config({"webhook_url": url}); console.print("[green]Saved.[/green]")
        elif choice == 'n':
            acc = TempMailAPI.generate_email()
            if acc:
                accounts.append(acc); Storage.save_accounts(accounts)
                # After generating, go back to the menu so the user sees it in their list
                # or we could go straight to view_loop, but the prompt implies 'b' should return to menu.
                view_loop(acc)
        elif choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(accounts):
                acc = accounts[idx]
                while True:
                    console.clear(); print_branded_banner()
                    console.print(f"\n[dim]Selected: {acc['email']}[/dim]\n  [white]v[/white] : View Inbox\n  [white]d[/white] : Delete\n  [white]b[/white] : Back")
                    sub = input("\n> ").strip().lower()
                    if sub == 'v': view_loop(acc)
                    elif sub == 'd':
                        if interactive_confirm(f"Delete {acc['email']}?"):
                            accounts.pop(idx); Storage.save_accounts(accounts)
                            break
                    elif sub == 'b': break

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--generate", action="store_true")
    parser.add_argument("--wait", help="Silent mode: Wait for keyword and exit")
    args = parser.parse_args()
    if args.generate:
        acc = TempMailAPI.generate_email()
        if acc: accounts = Storage.load_accounts(); accounts.append(acc); Storage.save_accounts(accounts); view_loop(acc)
        sys.exit()
    if args.wait:
        acc = TempMailAPI.generate_email()
        if acc: accounts = Storage.load_accounts(); accounts.append(acc); Storage.save_accounts(accounts); view_loop(acc, wait_keyword=args.wait)
        sys.exit()
    mail_menu()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(0)
