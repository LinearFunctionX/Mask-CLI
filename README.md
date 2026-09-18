Hi, 
dont we all hate giving our private information out for big companies that sell it to others?

this project started as a solo project because i hated the cycle of: 
1. create a new email
2. sign up for websites
3. get filled with spam 24/7
4. delete the email and start all over again.

And i needed a free open source solution...

# Mask-CLI

Instant privacy through temporary accounts.
A terminal-based tool for managing disposable email addresses and phone numbers.

## Installation

```bash
git clone https://github.com/LinearFunctionX/Mask-CLI.git
cd Mask-CLI
pip install requests beautifulsoup4 rich pyperclip
```

## Usage

Run the main menu:

```bash
python Mask.py
```

### Email Manager

```bash
python mask_mail.py # Interactive menu
python mask_mail.py -g # Generate and open a new email directly
python mask_mail.py --wait "keyword" # Wait for an email containing a keyword, then print and exit
```

### SMS Manager

```bash
python mask_sms.py # Interactive menu
python mask_sms.py -p # Pick a number from the public list directly
python mask_sms.py --wait "keyword" # Wait for an SMS containing a keyword, then print and exit
```

Key,  Action:
`↑` / `↓` Navigate messages
`Enter` View full message
`/` Search / filter
`c` Clear filter
`e` Export message to file
`b` Back to menu

## Configuration

- Accounts are stored in `~/.mask_mails.json` (email) and `~/.mask_numbers.json` (SMS)
- Webhook URL is stored in `~/.mask_config.json`

creditlematanhahaich