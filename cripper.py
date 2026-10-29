#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRIPPER-X v20.7 - THE HIJACK-PROOF WORDLIST ENGINE (LINUX)

ETHICAL USE ONLY. Test only systems you own or have explicit permission to audit.
"""
import os
import sys
import time
import signal
import random
import argparse
import threading
import gzip
import re
import itertools
import urllib.request
import subprocess
import shutil
import hashlib
import hmac
import tempfile
import shlex
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path

# ==============================================================================
# SECTION 1: COLORS, CONFIGURATION, LOGO
# ==============================================================================
_USE_COLOR = (
    sys.stdout.isatty()
    and not os.environ.get("NO_COLOR")
    and os.environ.get("TERM") != "dumb"
)
if _USE_COLOR:
    RED   = '\033[91m'
    GREEN = '\033[92m'
    WHITE = '\033[97m'
    GRAY  = '\033[90m'
    RESET = '\033[0m'
else:
    RED = GREEN = WHITE = GRAY = RESET = ''

VERSION      = "20.7"
GITHUB_REPO  = "YOUR_USERNAME/CRIPPER-X"   # builder overwrites
RSA_PUBLIC_N = 0                            # builder overwrites
RSA_PUBLIC_E = 65537

SHA256_DIGEST_INFO_PREFIX = bytes.fromhex(
    "3031300d060960864801650304020105000420"
)
SHA256_HASH_LEN = 32
MIN_PADDING_LEN = 8

WORKSPACE = "Cripper-X_Data"
SYMBOLS   = "!@#$%^&*()_+-=[]{}|;:',.<>/?`~"
NUMBERS   = sorted(list(set([str(i) for i in range(100)] +
                            [f"0{i}" for i in range(10)])), key=int)
YEARS     = [str(y) for y in range(1970, 2031)]
LEET_MAP  = {'a': ['a','4','@'], 'e': ['e','3'], 'i': ['i','1','!'],
             'o': ['o','0'], 's': ['s','5','$'], 't': ['t','7']}

MAX_PASSWORD_LEN    = 128
MAX_SCRAPE_BYTES    = 2 * 1024 * 1024
MAX_SCRAPE_SECONDS  = 30
MAX_FILE_BYTES      = 4 * 1024 * 1024
MAX_DOWNLOAD_BYTES  = 500 * 1024 * 1024
MAX_OSINT_WORDS     = 500
MAX_SEEN_ENTRIES    = 2_000_000
NET_TIMEOUT_SECONDS = 30

SPIDER_LOGO = rf"""{RED}
      /\                                 /\
     /  \_______________________________/  \
    /   /                               \   \
   /   /                                 \   \
  /   /   ▄████▄   ██▀███   ██▓ ██▓███     \   \
 /   /   ▒██▀ ▀█  ▓██ ▒ ██▒▓██▒▓██░  ██▒     \   \
/   /    ▒▓█    ▄ ▓██ ░▄█ ▒▒██▒▓██░ ██▓▒      \   \
\   \    ▒▓▓▄ ▄██▒▒██▀▀█▄  ░██░▒██▄█▓▒ ▒       \   \
 \   \   ▒ ▓███▀ ░░██▓ ▒██▒░██░▒██▒ ░  ░        /   /
  \   \  ░ ░▒ ▒  ░░ ▒▓ ░▒▓░░▓  ▒▓▒░ ░  ░       /   /
   \   \   ░  ▒     ░▒ ░ ▒░ ░  ░▒ ░           /   /
    \   \░          ░░   ░     ░░            /   /
     \   \                                  /   /
      \  /\  ▓█████ ▓█████▄  ██▓▒██   ██▒   /\  /
       \/  \ ▒██▀ ██▒██▀ ██▌▓██▒▒██  ██▒  /  \/
            \░██   █▌░██   █▌▒██▒▒██ ██░  /
             \░▓█▄   ▌░▓█▄   ▌░██░░ ███░ /
              \░▒████▓ ░▒████▓ ░██░░ ███░/
               \▒▒▓  ▒  ▒▒▓  ▒ ░▓  ░ ██▒/
                \░ ▒  ▒  ░ ▒  ▒  ░  ░ ██▒/
                 \░ ░  ░  ░ ░  ░     ░ ██▒/
                  \░       ░            ░ ▒░/
                   \                       /
                    \                     /
                     \                   /
                      \                 /
                       \               /
                        \             /
                         \           /
                          \         /
                           \       /
                            \     /
                             \   /
                              \ /
                               V{RESET}
{GREEN}                     C R I P P E R - X{RESET}
{GRAY}              [ S E C U R E   E N G I N E  v{VERSION} ]{RESET}
"""

ETHICS_BANNER = f"""{GREEN}
+-------------------------------------------------------------+
|  CRIPPER-X - FIRST-RUN ACKNOWLEDGEMENT                      |
+-------------------------------------------------------------+{RESET}
CRIPPER-X generates candidate wordlists from OSINT that you supply.
It is a dual-use security research tool.

By continuing, you agree that:

  1. You will only use CRIPPER-X against systems you own,
     or for which you have explicit written authorisation.
  2. You accept full legal responsibility for your use of
     this tool under your local jurisdiction.
  3. You understand that unauthorised access to computer
     systems is a criminal offence in most countries
     (CFAA in the US, Computer Misuse Act in the UK,
     §§202a/b StGB in Germany, Cybercrimes Act in NG, etc.).
  4. Your acceptance is logged LOCALLY only - CRIPPER-X
     never transmits anything about you.

{GRAY}Type 'y' to accept, anything else to abort.{RESET}
"""

SILENT_MODE = False


# ==============================================================================
# SECTION 1b: ETHICS ACKNOWLEDGEMENT
# ==============================================================================
def _ack_path():
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = xdg if xdg else os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "cripper" / "acknowledged"


def ethics_gate(args):
    if args.help or args.update or args.verify_installed is not None:
        return

    if args.yes:
        if not _ack_path().exists():
            _write_ack(args, reason="--yes")
        return

    ack = _ack_path()
    if ack.exists():
        return

    if not sys.stdin.isatty():
        print(f"{RED}[!] First-run acknowledgement required.{RESET}",
              file=sys.stderr)
        print(f"{RED}[!] Run once interactively, or pass --yes to accept.{RESET}",
              file=sys.stderr)
        sys.exit(1)

    print(ETHICS_BANNER, file=sys.stderr)
    try:
        answer = input("Accept? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer != "y":
        print(f"{RED}[!] Acknowledgement declined.  Exiting.{RESET}",
              file=sys.stderr)
        sys.exit(1)

    _write_ack(args, reason="interactive")


def _write_ack(args, reason):
    ack = _ack_path()
    try:
        ack.parent.mkdir(parents=True, exist_ok=True)
        try: os.chmod(ack.parent, 0o700)
        except PermissionError: pass
        record = (
            f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} "
            f"user={os.environ.get('USER') or os.environ.get('LOGNAME') or '?'} "
            f"host={os.uname().nodename} "
            f"version={VERSION} repo={GITHUB_REPO} "
            f"reason={reason} argv={' '.join(sys.argv[1:])}\n"
        )
        with open(ack, "a", encoding="utf-8") as f:
            f.write(record)
        try: os.chmod(ack, 0o600)
        except PermissionError: pass
    except OSError as e:
        sys.stderr.write(
            f"{RED}[!] Warning: could not write acknowledgement log ({e}).{RESET}\n"
            f"{RED}[!] Consent was accepted but NOT recorded.{RESET}\n"
        )


# ==============================================================================
# SECTION 2: SIGNATURE VERIFICATION (PKCS#1 v1.5 / SHA-256)
# ==============================================================================
def verify_signature(binary_path, sig_path):
    if RSA_PUBLIC_N == 0:
        return False, "Binary was not built with the official builder (RSA_PUBLIC_N=0)."

    try:
        with open(binary_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).digest()
        with open(sig_path, 'rb') as f:
            sig_bytes = f.read()

        key_size = (RSA_PUBLIC_N.bit_length() + 7) // 8
        if len(sig_bytes) != key_size:
            return False, f"Signature length {len(sig_bytes)} != key size {key_size}."

        sig_int = int.from_bytes(sig_bytes, 'big')
        if sig_int >= RSA_PUBLIC_N:
            return False, "Signature integer out of range."

        m  = pow(sig_int, RSA_PUBLIC_E, RSA_PUBLIC_N)
        em = m.to_bytes(key_size, 'big')

        # EM = 0x00 || 0x01 || PS (>=8 x 0xFF) || 0x00 || DigestInfo
        if len(em) < 11 or em[0] != 0x00 or em[1] != 0x01:
            return False, "Invalid PKCS#1 v1.5 header."

        sep_idx = em.find(b'\x00', 2)
        if sep_idx == -1:
            return False, "Separator not found in padding."

        ps_len = sep_idx - 2
        if ps_len < MIN_PADDING_LEN:
            return False, f"Padding too short ({ps_len} < {MIN_PADDING_LEN})."
        if not all(b == 0xFF for b in em[2:sep_idx]):
            return False, "Padding contains non-0xFF bytes."

        digest_info = em[sep_idx + 1:]
        expected_len = len(SHA256_DIGEST_INFO_PREFIX) + SHA256_HASH_LEN
        if len(digest_info) != expected_len:
            return False, f"DigestInfo length {len(digest_info)} != {expected_len}."
        if digest_info[:len(SHA256_DIGEST_INFO_PREFIX)] != SHA256_DIGEST_INFO_PREFIX:
            return False, "Invalid ASN.1 DigestInfo prefix."

        extracted_hash = digest_info[len(SHA256_DIGEST_INFO_PREFIX):]
        if hmac.compare_digest(extracted_hash, file_hash):
            return True, "Signature Valid."
        return False, "Hash mismatch - binary may be tampered."

    except Exception as e:
        return False, f"Verification Error: {e}"


# ==============================================================================
# SECTION 3: VERSION COMPARISON
# ==============================================================================
def _version_tuple(v):
    return tuple(int(p) for p in v.split("."))


def _cmp_versions(a, b):
    """Return -1, 0, or 1. Handles different-length tuples."""
    L = max(len(a), len(b))
    a = a + (0,) * (L - len(a))
    b = b + (0,) * (L - len(b))
    return (a > b) - (a < b)


# ==============================================================================
# SECTION 4: OSINT & MATH ENGINE
# ==============================================================================
class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.ignore_tags = {'script', 'style', 'head', 'title', 'meta', '[document]'}
        self.ignore_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag in self.ignore_tags:
            self.ignore_depth += 1
    def handle_endtag(self, tag):
        if tag in self.ignore_tags and self.ignore_depth > 0:
            self.ignore_depth -= 1
    def handle_data(self, data):
        if self.ignore_depth == 0:
            self.result.append(data)
    def get_text(self):
        return " ".join(self.result)


def safe_read_text(path, max_size=MAX_FILE_BYTES):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise RuntimeError(f"Cannot open '{path}': {e}")
    try:
        f = os.fdopen(fd, 'rb')
    except Exception:
        os.close(fd)
        raise
    with f:
        data = f.read(max_size)
    return data.decode('utf-8', errors='ignore')


def scrape_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': f'cripper-x/{VERSION} (+https://github.com/{GITHUB_REPO})',
        })
        buf = bytearray()
        deadline = time.time() + MAX_SCRAPE_SECONDS
        with urllib.request.urlopen(req, timeout=timeout) as response:
            while len(buf) < MAX_SCRAPE_BYTES and time.time() < deadline:
                chunk = response.read(min(64 * 1024, MAX_SCRAPE_BYTES - len(buf)))
                if not chunk:
                    break
                buf.extend(chunk)
        html = bytes(buf).decode('utf-8', errors='ignore')
        parser = HTMLTextExtractor()
        parser.feed(html)
        return re.sub(r'\s+', ' ', parser.get_text())
    except Exception:
        return ""


def _download(url, dest, timeout=NET_TIMEOUT_SECONDS, max_bytes=MAX_DOWNLOAD_BYTES):
    """Stream a URL to disk with timeout + size cap."""
    req = urllib.request.Request(url, headers={
        'User-Agent': f'cripper-x/{VERSION} (+https://github.com/{GITHUB_REPO})',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        # FIX: Content-Length pre-check now actually fires.  Skipped for
        # non-numeric values (e.g. chunked transfer-encoding).
        cl = r.headers.get("Content-Length")
        if cl and cl.isdigit() and int(cl) > max_bytes:
            raise ValueError(f"Download too large: {cl} bytes (max {max_bytes})")
        total = 0
        with open(dest, 'wb') as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Download exceeded {max_bytes} bytes")
                f.write(chunk)


def get_safe_leet(word):
    variants = ['']
    for char in word.lower():
        opts = LEET_MAP.get(char, [char])
        variants = [v + o for v in variants for o in opts]
        if len(variants) > 50:
            return random.sample(list(dict.fromkeys(variants)), min(5, len(variants)))
    return list(dict.fromkeys(variants))


def parse_length(length_str):
    parts = length_str.split('-')
    if len(parts) == 1:
        n = int(parts[0])
        if n < 1:
            raise ValueError("length must be >= 1")
        if n > MAX_PASSWORD_LEN:
            raise ValueError(f"length must be <= {MAX_PASSWORD_LEN}")
        return n, n
    if len(parts) == 2:
        a, b = int(parts[0]), int(parts[1])
        if a < 1 or b < 1:
            raise ValueError("lengths must be >= 1")
        if a > MAX_PASSWORD_LEN or b > MAX_PASSWORD_LEN:
            raise ValueError(f"lengths must be <= {MAX_PASSWORD_LEN}")
        return (a, b) if a <= b else (b, a)
    raise ValueError(f"expected N or N-M, got {length_str!r}")


def generate_passwords(context, length_str, known_chars, osint_data):
    try:
        min_len, max_len = parse_length(length_str)
    except (ValueError, TypeError) as e:
        log_msg(f"[!] Invalid --length '{length_str}' ({e}); using 6-12.", RED)
        min_len, max_len = 6, 12

    known_chars = [c.strip() for c in known_chars.split(',') if c.strip()]
    words = set()
    if context:
        words.update([w.strip().lower() for w in context.split(',') if w.strip()])

    STOP_WORDS = {'the','and','for','are','com','http','https','www','this','that',
                  'with','from','not','you','your','img','src','href','div','class',
                  'link','nav','copyright','html','php','css','javascript','button'}

    if osint_data:
        found_words = re.findall(r'\b[a-zA-Z0-9]{3,15}\b', osint_data)
        words.update([w.lower() for w in found_words
                      if not w.isdigit() and w.lower() not in STOP_WORDS])

    words = list(words)
    if not words:
        words = ["password", "admin"]

    if len(words) > MAX_OSINT_WORDS:
        log_msg(f"[!] OSINT produced {len(words)} words; capping to "
                f"{MAX_OSINT_WORDS} (longest first).", RED)
        words = sorted(words, key=lambda w: (-len(w), w))[:MAX_OSINT_WORDS]

    seen = OrderedDict()
    def is_valid(pwd):
        if not (min_len <= len(pwd) <= max_len):
            return False
        if pwd in seen:
            return False
        seen[pwd] = None
        if len(seen) > MAX_SEEN_ENTRIES:
            seen.popitem(last=False)
        return True

    suffixes = NUMBERS + ['123', '1234', '12345', '01', '007', '@123', '!@#']
    top_symbols = ['!', '@', '#', '$', '%', '&', '_', '-']
    top_years = YEARS

    if min_len <= 4 <= max_len:
        for i in range(10000):
            pwd = f"{i:04d}"
            if is_valid(pwd):
                yield pwd

    if min_len <= 6 <= max_len:
        top_6_pins = ['123456','000000','123123','654321','111111',
                      '121212','112233','159753','987654','777777']
        for pin in top_6_pins:
            if is_valid(pin):
                yield pin
        for i in range(100000, 100500):
            if is_valid(str(i)):
                yield str(i)

    for word in words:
        for yr in top_years:
            for sym in top_symbols:
                for variant in (word, word.capitalize(), word.upper()):
                    pwd = f"{variant}{yr}{sym}"
                    if is_valid(pwd):
                        yield pwd
            for suf in ('123', '01'):
                pwd = f"{word}{yr}{suf}"
                if is_valid(pwd):
                    yield pwd

    if len(words) >= 2:
        for w1, w2 in itertools.permutations(words, 2):
            for pwd in (f"{w1}{w2}", f"{w1}{w2}".capitalize()):
                if is_valid(pwd):
                    yield pwd
            for j in ('_', '.', '@', '-'):
                pwd = f"{w1}{j}{w2}"
                if is_valid(pwd):
                    yield pwd
                pwd2 = pwd.capitalize()
                if is_valid(pwd2):
                    yield pwd2

    if len(words) >= 3:
        for combo in itertools.islice(itertools.permutations(words, 3), 1000):
            pwd = "_".join(combo)
            if is_valid(pwd):
                yield pwd

    if known_chars:
        for word in words:
            for kc in known_chars:
                for pwd in (f"{word}{kc}", f"{word.capitalize()}{kc}", f"{kc}{word}"):
                    if is_valid(pwd):
                        yield pwd

    for word in words:
        base_variants = get_safe_leet(word) + [word.capitalize(), word.upper(), word[::-1]]
        for base in base_variants:
            if is_valid(base):
                yield base
            for suf in suffixes:
                pwd = base + suf
                if is_valid(pwd):
                    yield pwd
            for sym in top_symbols:
                pwd = base + sym
                if is_valid(pwd):
                    yield pwd
            if len(base) > 3:
                mid = len(base) // 2
                for sym in top_symbols[:5]:
                    pwd = base[:mid] + sym + base[mid:]
                    if is_valid(pwd):
                        yield pwd

    fail_count = 0
    while True:
        base = random.choice(words)
        mut = "".join(random.choice(LEET_MAP.get(c, [c])) for c in base)
        mut = "".join(c.upper() if random.random() < 0.3 else c.lower() for c in mut)
        while len(mut) < min_len:
            mut += random.choice(SYMBOLS + "0123456789")
        pwd = mut[:max_len]
        if is_valid(pwd):
            fail_count = 0
            yield pwd
        else:
            fail_count += 1
            if fail_count > 50000:
                return


# ==============================================================================
# SECTION 5: UI DASHBOARD
# ==============================================================================
def clear_screen():
    if SILENT_MODE:
        return
    sys.stdout.write('\033[H\033[J')
    sys.stdout.flush()


def log_msg(msg, color=""):
    if SILENT_MODE:
        sys.stderr.write(f"{color}{msg}{RESET}\n")
        sys.stderr.flush()
    else:
        print(f"{color}{msg}{RESET}")


def gui_dashboard(stats, stop_event):
    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()
    try:
        while not stop_event.is_set():
            clear_screen()
            print(SPIDER_LOGO)
            elapsed = time.time() - stats['start_time']
            speed = int(stats['generated'] / elapsed) if elapsed > 0 else 0

            print(f"{RED}+- ACTIVE ATTACK ---------------------+ "
                  f"{RED}+- TOP CANDIDATES --------------------+{RESET}")
            print(f"{RED}|{RESET} Status:  {GREEN}Generating...{RESET}               "
                  f"{RED}| {RED}|{RESET}")
            print(f"{RED}|{RESET} Speed:   {GREEN}{speed:>12,} p/s{RESET}         "
                  f"{RED}| {RED}|{RESET}")
            print(f"{RED}|{RESET} Written: {GREEN}{stats['written']:>12,}{RESET}         "
                  f"{RED}| {RED}|{RESET}")

            tops = stats.get('top', [])[:5]
            for j in range(5):
                left = ""
                right = f"{GREEN}{tops[j]:<20}{RESET}" if j < len(tops) else ""
                print(f"{RED}|{RESET}{left:<38} {RED}| {RED}|{RESET} "
                      f"{right:<36} {RED}|{RESET}")

            print(f"{RED}+--------------------------------------+ "
                  f"{RED}+--------------------------------------+{RESET}")
            print(f"\n  {GREEN}[ {spinner[i % len(spinner)]} ]{RESET} "
                  f"Streaming payload... {RED}Press Ctrl+C to abort.{RESET}")
            i += 1
            time.sleep(0.3)
    finally:
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()


# ==============================================================================
# SECTION 6: OUTPUT COMMIT / DISCARD / PARTIAL
# ==============================================================================
def _commit_output(f, tmp_path, final_path, is_stdout):
    """Success path: flush, fsync, close, atomic-replace, fsync dir."""
    if is_stdout:
        try: f.flush()
        except Exception: pass
        return
    f.flush()
    try: os.fsync(f.fileno())
    except OSError: pass
    f.close()
    os.replace(tmp_path, final_path)
    try:
        dfd = os.open(os.path.dirname(final_path) or ".",
                      os.O_DIRECTORY | os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    except OSError:
        pass


def _save_partial(f, tmp_path, final_path, is_stdout):
    """Ctrl+C path: save whatever we have."""
    try:
        f.flush()
        if not is_stdout:
            try: os.fsync(f.fileno())
            except OSError: pass
            f.close()
            os.replace(tmp_path, final_path)
    except Exception:
        try: f.close()
        except Exception: pass


def _discard_partial(f, tmp_path, is_stdout):
    """Error path: close and delete tmp file -- never commit a partial
    result.  Does NOT close stdout (would break subsequent log output)."""
    if is_stdout:
        return
    try: f.close()
    except Exception: pass
    if tmp_path:
        try: os.remove(tmp_path)
        except OSError: pass


# ==============================================================================
# SECTION 7: INSTALL-PATH RESOLUTION
# ==============================================================================
def _resolve_install_path(explicit):
    if explicit:
        if not os.path.isabs(explicit):
            raise ValueError(f"--install-path must be absolute: {explicit}")
        return os.path.realpath(explicit)

    found = shutil.which("cripper")
    if found:
        return os.path.realpath(found)

    argv0 = os.path.realpath(sys.argv[0])
    if os.path.basename(argv0) == "cripper" and os.access(argv0, os.X_OK):
        return argv0

    return "/usr/local/bin/cripper"


# ==============================================================================
# SECTION 8: MAIN
# ==============================================================================
def main():
    global SILENT_MODE

    parser = argparse.ArgumentParser(description="CRIPPER-X Wordlist Engine",
                                     add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--version", action="store_true",
                        help="Show version")
    parser.add_argument("--update", action="store_true",
                        help="Download latest signed binary")
    parser.add_argument("--install-path", metavar="PATH",
                        help="Override install location for --update")
    parser.add_argument("--verify-installed", nargs="?", const="", default=None,
                        metavar="PATH",
                        help="Verify a binary against its GitHub signature")
    parser.add_argument("-c", "--context", type=str)
    parser.add_argument("-l", "--length", type=str, default="6-12")
    parser.add_argument("-k", "--known", type=str, default="")
    parser.add_argument("-o", "--out", type=str, default="cripperx_payload.txt")
    parser.add_argument("--osint", type=str, action="append")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--gzip", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Pre-accept the ethics acknowledgement")

    if len(sys.argv) == 1:
        sys.argv.append("--help")

    args = parser.parse_args()

    SILENT_MODE = (
        args.stdout
        or (not sys.stdout.isatty())
        or os.environ.get("TERM") == "dumb"
    )

    # ---------------------------------------------------------- --help
    if args.help:
        clear_screen()
        print(SPIDER_LOGO)
        print(f"""{WHITE}USAGE:{RESET}
  cripper [OPTIONS]
  cripper -c yam,egg -l 6 -k @,9 --gui

{WHITE}OPTIONS:{RESET}
  {GREEN}-h, --help{RESET}                    Show this manual
  {GREEN}-v, --version{RESET}                 Show version
  {GREEN}--update{RESET}                      Download latest signed binary from GitHub
  {GREEN}--install-path PATH{RESET}           Override install location for --update
  {GREEN}--verify-installed [PATH]{RESET}     Verify a binary (default: installed 'cripper')
  {GREEN}-c, --context{RESET}                 Context words (comma separated)
  {GREEN}-l, --length{RESET}                  Exact length (8) or Range (6-12); max {MAX_PASSWORD_LEN}
  {GREEN}-k, --known{RESET}                   Known characters (e.g. @,9)
  {GREEN}-o, --out{RESET}                     Output filename
  {GREEN}--osint{RESET}                       Multiple URLs or local files
  {GREEN}--gui{RESET}                         Show the animated dashboard
  {GREEN}--gzip{RESET}                        Compress the wordlist
  {GREEN}--stdout{RESET}                      Print to terminal (pipe to hashcat)
  {GREEN}--max{RESET}                         Max passwords to generate
  {GREEN}--yes, -y{RESET}                     Pre-accept the ethics acknowledgement

{WHITE}EXAMPLES:{RESET}
  {GRAY}# Fast generation with GUI{RESET}
  cripper -c yam,egg -l 6 --gui

  {GRAY}# OSINT Scrape{RESET}
  cripper --osint https://github.com/torvalds -l 8 --gui

  {GRAY}# Pipe to hashcat{RESET}
  cripper -c yam -l 8 --stdout | hashcat -m 0 hashes.txt

  {GRAY}# Audit your installation{RESET}
  cripper --verify-installed

{WHITE}ETHICS:{RESET}
  The first interactive run prompts for acknowledgement; the acceptance
  is logged locally to $XDG_CONFIG_HOME/cripper/acknowledged (mode 0600).
  Nothing is transmitted.  Delete the file to reset the prompt.
""")
        sys.exit(0)

    # ---------------------------------------------------------- --version
    if args.version:
        print(f"CRIPPER-X v{VERSION}")
        sys.exit(0)

    # ---------------------------------------------------------- --update
    if args.update:
        if RSA_PUBLIC_N == 0:
            print(f"{RED}[!] This binary was NOT built with the official builder.{RESET}")
            print(f"{RED}[!] Refusing to self-update.  Reinstall from a trusted source.{RESET}")
            sys.exit(1)

        try:
            install_path = _resolve_install_path(args.install_path)
        except ValueError as e:
            print(f"{RED}[!] {e}{RESET}")
            sys.exit(1)

        staging = install_path + ".new"

        print(f"{GREEN}[*] Contacting GitHub for latest Linux release...{RESET}")
        print(f"{GRAY}[*] Target install path: {install_path}{RESET}")
        url_bin = f"https://github.com/{GITHUB_REPO}/releases/latest/download/cripper"
        url_sig = f"https://github.com/{GITHUB_REPO}/releases/latest/download/cripper.sig"

        fd, tmp_bin = tempfile.mkstemp(prefix="cripper_")
        os.close(fd)
        fd, tmp_sig = tempfile.mkstemp(prefix="cripper_sig_")
        os.close(fd)
        installed = False

        try:
            print(f"{GREEN}[*] Requesting sudo privileges...{RESET}")
            subprocess.run(["sudo", "-v"], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"{RED}[!] sudo unavailable or authentication failed: {e}{RESET}")
            for p in (tmp_bin, tmp_sig):
                try: os.remove(p)
                except Exception: pass
            sys.exit(1)

        try:
            print(f"{GREEN}[+] Downloading binary and signature...{RESET}")
            _download(url_bin, tmp_bin)
            _download(url_sig, tmp_sig)

            print(f"{GREEN}[*] Verifying signature (PKCS#1 v1.5 / SHA-256)...{RESET}")
            ok, msg = verify_signature(tmp_bin, tmp_sig)
            if not ok:
                print(f"{RED}[!] SECURITY ALERT: {msg}{RESET}")
                print(f"{RED}[!] Update aborted.{RESET}")
                sys.exit(1)
            print(f"{GREEN}[+] {msg}{RESET}")

            print(f"{GREEN}[*] Staging binary at {staging}...{RESET}")
            subprocess.run(["sudo", "rm", "-f", staging], check=False)
            subprocess.run(["sudo", "install", "-m", "0755", tmp_bin, staging],
                           check=True)

            try:
                r = subprocess.run([staging, "--version"],
                                   capture_output=True, text=True, timeout=15)
                probe = r.stdout + r.stderr
            except Exception as e:
                print(f"{RED}[!] Version probe failed ({e}).  Aborting.{RESET}")
                subprocess.run(["sudo", "rm", "-f", staging], check=False)
                sys.exit(1)

            m = re.search(r"CRIPPER-X v(\d+(?:\.\d+)*)", probe)
            if not m:
                print(f"{RED}[!] New binary did not report a CRIPPER-X version.{RESET}")
                subprocess.run(["sudo", "rm", "-f", staging], check=False)
                sys.exit(1)

            cmp = _cmp_versions(_version_tuple(m.group(1)), _version_tuple(VERSION))
            if cmp < 0:
                print(f"{RED}[!] Refusing downgrade: v{m.group(1)} < v{VERSION}{RESET}")
                subprocess.run(["sudo", "rm", "-f", staging], check=False)
                sys.exit(1)
            if cmp == 0:
                print(f"{GREEN}[=] Already up to date (v{VERSION}).{RESET}")
                subprocess.run(["sudo", "rm", "-f", staging], check=False)
                sys.exit(0)

            print(f"{GREEN}[+] Installing update -> {install_path}{RESET}")
            subprocess.run(["sudo", "mv", "-f", staging, install_path], check=True)
            installed = True
            print(f"{GREEN}[+] Update Complete -> {install_path}{RESET}")

        except Exception as e:
            print(f"{RED}[!] Update failed: {e}{RESET}")
        finally:
            for p in (tmp_bin, tmp_sig):
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except Exception: pass
            if not installed:
                subprocess.run(["sudo", "rm", "-f", staging], check=False)
        sys.exit(0 if installed else 1)

    # ---------------------------------------------------- --verify-installed
    if args.verify_installed is not None:
        if RSA_PUBLIC_N == 0:
            print(f"{RED}[!] RSA public key not embedded.  Cannot verify.{RESET}")
            sys.exit(1)

        if args.verify_installed:
            inst = os.path.realpath(args.verify_installed)
            if not os.path.isfile(inst):
                print(f"{RED}[!] Not a regular file: {args.verify_installed}{RESET}")
                sys.exit(1)
        else:
            argv0 = os.path.realpath(sys.argv[0])
            if os.path.basename(argv0) == "cripper" and os.access(argv0, os.X_OK):
                inst = argv0
            else:
                found = shutil.which("cripper")
                if not found:
                    print(f"{RED}[!] Could not locate 'cripper'.{RESET}")
                    print(f"{RED}[!] Re-run with: cripper --verify-installed /path/to/cripper{RESET}")
                    sys.exit(1)
                inst = os.path.realpath(found)

        # FIX: probe the target file's version so we fetch the matching
        # signature.  Without this, verifying a v20.8 binary from a v20.7
        # runner fetches v20.7/cripper.sig and produces a false "tampered".
        inst_version = "unknown"
        try:
            r = subprocess.run([inst, "--version"],
                               capture_output=True, text=True, timeout=10)
            vm = re.search(r"CRIPPER-X v(\d+(?:\.\d+)*)", r.stdout + r.stderr)
            if vm:
                inst_version = vm.group(1)
        except Exception:
            pass

        if inst_version == "unknown":
            print(f"{RED}[!] Could not determine the target binary's version.{RESET}")
            print(f"{RED}[!] Cannot determine which signature to fetch.{RESET}")
            print(f"{RED}[!] Is '{inst}' a CRIPPER-X binary?{RESET}")
            sys.exit(1)

        print(f"{GREEN}[*] Verifying {inst}{RESET}")
        print(f"{GRAY}    file reports: v{inst_version}{RESET}")
        print(f"{GRAY}    running:      v{VERSION}{RESET}")

        url_sig = (f"https://github.com/{GITHUB_REPO}/releases/download/"
                   f"v{inst_version}/cripper.sig")
        fd, tmp_sig = tempfile.mkstemp(prefix="cripper_sig_")
        os.close(fd)
        try:
            print(f"{GREEN}[*] Fetching signature: {url_sig}{RESET}")
            _download(url_sig, tmp_sig)
            ok, msg = verify_signature(inst, tmp_sig)
            print((f"{GREEN}[+] {msg}{RESET}") if ok else (f"{RED}[!] {msg}{RESET}"))
            sys.exit(0 if ok else 1)
        except Exception as e:
            print(f"{RED}[!] verify-installed failed: {e}{RESET}")
            sys.exit(1)
        finally:
            try: os.remove(tmp_sig)
            except FileNotFoundError: pass

    # ---------------------------------------------------- ethics gate
    ethics_gate(args)

    # ------------------------------------------------------ workspace setup
    try:
        os.makedirs(WORKSPACE, exist_ok=True)
    except OSError as e:
        log_msg(f"[!] Cannot create workspace '{WORKSPACE}': {e}", RED)
        log_msg("[!] Run cripper from a writable directory.", RED)
        sys.exit(1)

    safe_out_name = os.path.basename(args.out.rstrip("/")) or "cripperx_payload.txt"
    final_path = os.path.join(WORKSPACE, safe_out_name)
    if args.gzip and not final_path.lower().endswith(".gz"):
        final_path += ".gz"

    osint_text = ""
    if args.osint:
        for item in args.osint:
            if item.startswith("http"):
                log_msg(f"[+] Scraping OSINT from: {item}", GREEN)
                text = scrape_url(item)
                if text:
                    log_msg(f"[+] Extracted {len(text)} characters.", GREEN)
                    osint_text += " " + text
                else:
                    log_msg(f"[!] Scrape failed: {item}", RED)
            else:
                if not os.path.isfile(item):
                    log_msg(f"[!] Not a regular file: {item}", RED)
                    continue
                try:
                    osint_text += " " + safe_read_text(item)
                    log_msg(f"[+] Loaded OSINT file: {item}", GREEN)
                except Exception as e:
                    log_msg(f"[!] Could not read {item}: {e}", RED)

        if not osint_text.strip():
            log_msg("[!] No OSINT data extracted.", RED)

    stats = {'generated': 0, 'written': 0, 'start_time': time.time(), 'top': []}
    stop_event = threading.Event()

    if args.gui and not SILENT_MODE:
        threading.Thread(target=gui_dashboard, args=(stats, stop_event),
                         daemon=True).start()
    elif not SILENT_MODE:
        clear_screen()
        print(SPIDER_LOGO)
        log_msg("[+] Engine Started.  Generating payload...", GREEN)

    # ------------------------------------------------------------ output
    if args.stdout:
        out_f = sys.stdout
        tmp_path = None
    else:
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=os.path.basename(final_path) + ".",
                suffix=".tmp",
                dir=os.path.dirname(final_path) or ".",
            )
            os.close(fd)
            if args.gzip:
                out_f = gzip.open(tmp_path, 'wt', encoding='utf-8', buffering=1 << 20)
            else:
                out_f = open(tmp_path, 'w', encoding='utf-8', buffering=1 << 20)
        except Exception as e:
            log_msg(f"[!] Cannot open output: {e}", RED)
            sys.exit(1)

    # -------------------------------------------------------- generation
    interrupted = False
    try:
        for pwd in generate_passwords(args.context, args.length,
                                      args.known, osint_text):
            stats['generated'] += 1
            out_f.write(pwd + "\n")
            stats['written'] += 1

            if len(pwd) >= 6 and not pwd.isdigit():
                if len(stats['top']) < 5:
                    stats['top'].append(pwd)
                else:
                    stats['top'].pop(0)
                    stats['top'].append(pwd)

            if stats['generated'] % 50000 == 0:
                out_f.flush()
            if args.max > 0 and stats['written'] >= args.max:
                break

    except KeyboardInterrupt:
        interrupted = True
        _save_partial(out_f, tmp_path, final_path, args.stdout)
    except Exception as e:
        _discard_partial(out_f, tmp_path, args.stdout)
        stop_event.set()
        log_msg(f"[!] A CRITICAL ERROR OCCURRED: {e}", RED)
        log_msg("[!] Partial output discarded.", RED)
        sys.exit(1)
    else:
        try:
            _commit_output(out_f, tmp_path, final_path, args.stdout)
        except Exception as e:
            stop_event.set()
            log_msg(f"[!] Could not finalize output: {e}", RED)
            sys.exit(1)

    stop_event.set()
    time.sleep(0.3)

    if not SILENT_MODE:
        clear_screen()
        print(SPIDER_LOGO)
        if interrupted:
            log_msg("[!] GENERATION ABORTED BY USER (partial saved).", RED)
        else:
            log_msg("[OK] GENERATION COMPLETE", GREEN)
        shown = 'STDOUT' if args.stdout else final_path
        log_msg(f"File:    {shown}", GRAY)
        label = "Unique" if stats['written'] <= MAX_SEEN_ENTRIES else "Written"
        log_msg(f"{label}: {stats['written']:,}", GREEN)
        if not args.stdout:
            print(f"\n{RED}  [!] Feed to hashcat:{RESET}")
            print(f"  hashcat -a 0 -m 0 hashes.txt {shlex.quote(final_path)}\n")

    sys.exit(0 if not interrupted else 130)


def _shutdown(signum, frame):
    """Treat SIGTERM like Ctrl+C so partial output is finalized."""
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _shutdown)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}An unexpected error occurred: {e}{RESET}")
        sys.exit(1)
