# CRIPPER-X 🕷️

**Context-aware OSINT wordlist generator with a cryptographically hijack-proof self-updater.**

CRIPPER-X is a high-performance wordlist engine designed for authorized security auditing, CTFs, and penetration testing. It takes context words, known characters, and live OSINT scraping to generate highly targeted password candidates.

## ✨ Features

- **Blazing Fast:** Compiled into a standalone Linux binary (no Python required to run).
- **OSINT Scraper:** Pass URLs or local files directly to the engine to extract real-world words and context.
- **Advanced Mutation:** Automatically applies Leetspeak, capitalization, years, and symbols to maximize hit rates.
- **Live Dashboard:** Beautiful, real-time CLI dashboard (`--gui`) to monitor speed and top candidates.
- **Hijack-Proof Security:** Every binary is cryptographically signed with RSA-2048. The built-in updater verifies the signature before installing.
- **Memory Safe:** Built-in limits for length, OSINT word counts, and response sizes to prevent DoS.

## 📦 Installation

### The Fast Way (Recommended)
Open your Linux terminal and run this single command. It will download the latest binary, verify the SHA-256 checksum and RSA signature, and install it to `/usr/local/bin/`.

```bash
curl -sSL https://raw.githubusercontent.com/Bli1-95CHIB/CRIPPER-X/main/install.sh | bash


Manual Installation

If you prefer to download manually, grab the cripper binary from the Releases page, then:

```bash
chmod +x cripper
sudo mv cripper /usr/local/bin/
```

🚀 Usage

Run cripper --help to see all options.

Basic Generation

Generate passwords using context words and known characters:

```bash
cripper -C admin,root -k @,9 -l 6-10
```

OSINT Scraping

Scrape a target's website and generate passwords based on their public data:

```bash
cripper --osint https://example.com -l 8-12 --gui
```

Pipe to Hashcat

Generate passwords directly into Hashcat:

```bash
cripper -C companyname -l 8 --stdout | hashcat -m 0 hashes.txt
```

🛡️ Security & Verification

CRIPPER-X is designed to be hijack-proof. Even if GitHub or the repository is compromised, attackers cannot push a malicious update because they do not have the developer's private.pem.

You can verify your installed binary at any time:

```bash
cripper --verify-installed
```

If it prints [+] Signature Valid., your binary is exactly as it was when the developer compiled it.

⚖️ Disclaimer

ETHICAL USE ONLY. This tool is provided for educational purposes, CTF challenges, and authorized security auditing only. The author is not responsible for any misuse or damage caused by this tool. Do not use this tool against systems you do not own or have explicit permission to test.
