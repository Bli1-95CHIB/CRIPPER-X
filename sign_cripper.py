#!/usr/bin/env python3
"""
CRIPPER-X Linux Automated Builder & Signer (Hijack-Proof)

Builds cripper.py -> cripper binary, signs with RSA-2048 (PKCS#1 v1.5),
emits cripper.sha256 for second-channel publication.

Refuses to build a version whose tag already exists (local or remote),
which prevents the silent "user stuck on old binary" failure mode.

Linux only. Requires: openssl, python3, pip install nuitka
"""
import os
import re
import sys
import argparse
import hashlib
import subprocess
from pathlib import Path

BUILD_DIR   = Path.cwd()
PRIVATE_KEY = BUILD_DIR / "private.pem"
SRC_FILE    = BUILD_DIR / "cripper.py"
PATCHED     = BUILD_DIR / "cripper_patched.py"
BINARY      = BUILD_DIR / "cripper"
SIG_FILE    = BUILD_DIR / "cripper.sig"
SHA_FILE    = BUILD_DIR / "cripper.sha256"
TMP_PUB     = BUILD_DIR / "tmp_pub.pem"

MIN_KEY_BITS = 2048


# ------------------------------------------------------------- helpers
def warn(msg): print(f"[!] {msg}", file=sys.stderr)
def info(msg): print(f"[*] {msg}")
def ok(msg):   print(f"[+] {msg}")


def run_cmd(cmd, shell=False, env=None):
    """Return (ok, stdout, stderr). Never swallow diagnostics."""
    try:
        r = subprocess.run(
            cmd, check=True, shell=shell, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        return True, r.stdout or "", r.stderr or ""
    except FileNotFoundError as e:
        return False, "", f"Command not found: {e}"
    except subprocess.CalledProcessError as e:
        return False, e.stdout or "", e.stderr or str(e)


def cleanup_on_fail(*, delete_binary=False):
    """Remove stale build artifacts. Only delete the binary when we know it
    was produced by this (failed) build -- protects a valid previous binary."""
    for p in (SIG_FILE, SHA_FILE, PATCHED, TMP_PUB):
        try: p.unlink()
        except FileNotFoundError: pass
    if delete_binary:
        try: BINARY.unlink()
        except FileNotFoundError: pass


def check_git_safety():
    """Verify private.pem is git-ignored and untracked."""
    good, out, _ = run_cmd(["git", "rev-parse", "--show-toplevel"])
    if not good:
        return
    repo_root = Path(out.strip())

    try:
        rel = PRIVATE_KEY.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return

    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "check-ignore", "-q", str(rel)],
            capture_output=True,
        )
        if r.returncode != 0:
            warn(f"'{rel}' is NOT git-ignored.  Add it to .gitignore before committing.")
    except FileNotFoundError:
        pass
    except Exception as e:
        warn(f"Could not run 'git check-ignore': {e}")

    good2, out2, _ = run_cmd(
        ["git", "-C", str(repo_root), "ls-files", "--", str(rel)]
    )
    if good2 and out2.strip():
        warn(f"'{rel}' IS tracked by git!  Run:")
        warn(f"    git -C {repo_root} rm --cached {rel}")


# -------------------------------------------------- tag-collision guard
def _in_git_repo():
    good, _, _ = run_cmd(["git", "rev-parse", "--show-toplevel"])
    return good


def _next_version(v):
    """Suggest the next version for a bump. Preserves the patch component
    when the version already has three parts."""
    parts = v.split(".")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return "X.Y (bump manually)"
    if len(nums) == 1:
        return f"{nums[0] + 1}.0"
    if len(nums) == 2:
        return f"{nums[0]}.{nums[1] + 1}"
    nums[-1] += 1
    return ".".join(str(n) for n in nums)


def check_tag_collision(version, force=False):
    """Refuse to build if v{version} exists locally or on origin."""
    if not _in_git_repo():
        info("Not in a git repo -- skipping tag collision check.")
        return

    good, out, _ = run_cmd(["git", "tag", "-l", f"v{version}"])
    local_exists = good and out.strip()

    remote_exists = False
    if not local_exists:
        try:
            good2, out2, _ = run_cmd(
                ["git", "ls-remote", "--tags", "--exit-code", "origin",
                 f"refs/tags/v{version}"],
            )
            remote_exists = good2 and out2.strip()
        except Exception:
            pass

    if not (local_exists or remote_exists):
        ok(f"No existing tag v{version} -- safe to build.")
        return

    where = "locally" if local_exists else "on origin"
    warn(f"Tag v{version} already exists ({where}).")
    warn("")
    warn("You are about to build a binary whose version matches an")
    warn("already-published release.  Consequences:")
    warn(f"  - Users running the old v{version} binary CANNOT --update")
    warn(f"    (they will see 'already up to date' forever)")
    warn(f"  - GitHub will reject a release with the same tag")
    warn(f"  - --verify-installed fetches v{version}/cripper.sig, so")
    warn(f"    the OLD signature is used against the NEW binary and")
    warn(f"    verification FAILS for every user")
    warn("")
    warn(f"Recommended: bump VERSION in cripper.py to \"{_next_version(version)}\"")
    warn("")
    warn(f"To rebuild the SAME version anyway, first delete the tag and")
    warn(f"release from GitHub, then run:")
    warn(f"    git tag -d v{version}")
    warn(f"    git push origin :refs/tags/v{version}")
    warn("")

    if force:
        warn("--force supplied.  Proceeding despite tag collision.")
        return

    if os.environ.get("CRIPPER_ALLOW_TAG_COLLISION") == "1":
        warn("CRIPPER_ALLOW_TAG_COLLISION=1 set.  Proceeding.")
        return

    if not sys.stdin.isatty():
        warn("Non-interactive shell -- refusing to build with colliding tag.")
        warn("Set CRIPPER_ALLOW_TAG_COLLISION=1 to override (not recommended).")
        sys.exit(1)

    answer = input("Continue anyway (not recommended)? [y/N]: ").strip().lower()
    if answer != "y":
        info("Aborted by user.")
        sys.exit(1)
    warn("Proceeding despite tag collision.  You were warned.")


# ----------------------------------------------------- modulus / source
def extract_modulus():
    """Robust modulus extraction -- works on OpenSSL 1.1.x and 3.x."""
    good, out, err = run_cmd(
        ["openssl", "rsa", "-in", str(PRIVATE_KEY), "-modulus", "-noout"],
        shell=False,
    )
    if not good:
        warn(f"openssl rsa failed:\n{err}")
        return None
    combined = (out or "") + "\n" + (err or "")
    m = re.search(r"Modulus\s*=\s*([0-9A-Fa-f]+)", combined)
    if not m:
        warn("Could not parse modulus.  Raw output was:")
        print(combined, file=sys.stderr)
        return None
    return int(m.group(1), 16)


def read_declared_version(code):
    """Extract VERSION from cripper.py. Accepts single or double quotes."""
    m = re.search(r'''^VERSION\s*=\s*["']([\d.]+)["']''', code, re.MULTILINE)
    return m.group(1) if m else None


def read_source_and_version():
    """Read cripper.py once, return (code, version).  Used so we can check
    the tag collision BEFORE mutating anything on disk."""
    if not SRC_FILE.exists():
        warn(f"{SRC_FILE.name} not found in {BUILD_DIR}")
        sys.exit(1)
    code = SRC_FILE.read_text(encoding="utf-8")
    version = read_declared_version(code)
    if not version:
        warn("Could not find VERSION in cripper.py -- refusing to build.")
        sys.exit(1)
    return code, version


def patch_source(code, modulus_int, repo):
    """Patch the pre-read source and write cripper_patched.py."""
    new_code = re.sub(r"RSA_PUBLIC_N\s*=\s*\d+", f"RSA_PUBLIC_N = {modulus_int}", code)
    new_code = re.sub(r'GITHUB_REPO\s*=\s*".*?"', f'GITHUB_REPO = "{repo}"', new_code)

    if new_code == code:
        warn("Patch did not apply -- regex did not match.  Aborting.")
        sys.exit(1)
    if "RSA_PUBLIC_N = 0" in new_code or "YOUR_USERNAME/CRIPPER-X" in new_code:
        warn("Patched file still contains placeholder values.  Refusing to build.")
        sys.exit(1)

    PATCHED.write_text(new_code, encoding="utf-8")
    ok("Patch applied and verified.")


# ------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(
        description="CRIPPER-X builder: patch, compile, sign, checksum"
    )
    parser.add_argument("--repo", metavar="OWNER/NAME",
                        help="GitHub repo (default: prompt interactively)")
    parser.add_argument("--force", action="store_true",
                        help="Allow rebuilding an existing version tag "
                             "(NOT recommended -- users will be stuck)")
    args = parser.parse_args()

    print("[*] CRIPPER-X Linux Builder (Hijack-Proof)")
    print("[*] Starting automated build process...\n")

    # 0. Repo
    repo = args.repo
    if not repo:
        repo = input("[?] GitHub repository (e.g. YourName/CRIPPER-X): ").strip()
    if not repo or "/" not in repo or repo.startswith("YOUR_"):
        warn("Invalid or placeholder repo -- refusing to build.")
        sys.exit(1)
    info(f"Repo: {repo}")

    # 1. OpenSSL
    if not run_cmd(["openssl", "version"])[0]:
        warn("OpenSSL missing.  Run:  sudo apt install openssl")
        sys.exit(1)

    # 2. Keys -- always enforce 0600
    if not PRIVATE_KEY.exists():
        info("Generating RSA-2048 keypair (one-time)...")
        good, _, err = run_cmd(
            ["openssl", "genrsa", "-out", str(PRIVATE_KEY), "2048"]
        )
        if not good:
            warn(f"Key generation failed:\n{err}")
            sys.exit(1)
        ok("Keys generated.  KEEP 'private.pem' SECRET.")
    else:
        info("Existing 'private.pem' found.")

    try:
        os.chmod(PRIVATE_KEY, 0o600)
    except PermissionError as e:
        warn(f"Cannot chmod {PRIVATE_KEY}: {e}")
        warn(f"Fix ownership:  sudo chown $(id -u):$(id -g) {PRIVATE_KEY}")
        sys.exit(1)

    check_git_safety()

    # 3. Modulus + size enforcement
    info("Extracting public modulus...")
    modulus_int = extract_modulus()
    if modulus_int is None:
        sys.exit(1)

    bits = modulus_int.bit_length()
    if bits < MIN_KEY_BITS:
        warn(f"Refusing to sign with a {bits}-bit key (min {MIN_KEY_BITS}).")
        warn("Regenerate:  mv private.pem private.pem.old && "
             "openssl genrsa -out private.pem 2048")
        sys.exit(1)
    ok(f"Modulus: {bits} bits")

    # 4. Read source and check tag collision BEFORE any file is written.
    code, version = read_source_and_version()
    info(f"Building version {version}")

    info("Checking for existing version tag...")
    check_tag_collision(version, force=args.force)

    # 5. Patch source
    info("Patching cripper.py...")
    patch_source(code, modulus_int, repo)

    # 6. Compile -- deterministic SOURCE_DATE_EPOCH from git commit
    info("Compiling with Nuitka (this takes a few minutes)...")
    env = os.environ.copy()
    good, out, _ = run_cmd(["git", "log", "-1", "--format=%ct", "HEAD"])
    if good and out.strip():
        env.setdefault("SOURCE_DATE_EPOCH", out.strip())
    else:
        env.setdefault("SOURCE_DATE_EPOCH", str(int(SRC_FILE.stat().st_mtime)))

    compile_cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile", "--lto=yes",
        "--assume-yes-for-downloads",
        "--output-filename=cripper",
        "--output-dir=.",
        "cripper_patched.py",
    ]
    good, _, err = run_cmd(compile_cmd, env=env)
    if not good:
        warn(f"Nuitka failed:\n{err}")
        warn("Install Nuitka:  pip install nuitka")
        cleanup_on_fail()
        sys.exit(1)
    if not BINARY.exists():
        warn("Compile reported success but binary is missing.  Aborting.")
        cleanup_on_fail()
        sys.exit(1)
    ok(f"Binary: {BINARY} ({BINARY.stat().st_size:,} bytes)")

    # 6b. Assert binary reports same version as source (anchored regex)
    try:
        r = subprocess.run([str(BINARY), "--version"],
                           capture_output=True, text=True, timeout=15)
        reported = (r.stdout + r.stderr)
    except Exception as e:
        warn(f"Could not probe built binary version: {e}")
        cleanup_on_fail(delete_binary=True)
        sys.exit(1)

    if not re.search(rf"CRIPPER-X v{re.escape(version)}(?![\w.])", reported):
        warn(f"Built binary reports '{reported.strip()[:80]}' -- "
             f"expected v{version}.  Aborting.")
        cleanup_on_fail(delete_binary=True)
        sys.exit(1)
    ok(f"Binary self-reports v{version}")

    # 7-9: sign, self-verify, checksum
    try:
        info("Signing...")
        good, _, err = run_cmd([
            "openssl", "dgst", "-sha256", "-sign", str(PRIVATE_KEY),
            "-out", str(SIG_FILE), str(BINARY),
        ])
        if not good:
            warn(f"Signing failed:\n{err}")
            raise SystemExit(1)
        ok(f"Signature: {SIG_FILE} ({SIG_FILE.stat().st_size} bytes)")

        info("Self-verifying...")
        good, _, err = run_cmd([
            "openssl", "rsa", "-in", str(PRIVATE_KEY),
            "-pubout", "-out", str(TMP_PUB),
        ])
        if not good or not TMP_PUB.exists():
            warn(f"Public key export failed:\n{err}")
            raise SystemExit(1)

        good, out, err = run_cmd([
            "openssl", "dgst", "-sha256", "-verify", str(TMP_PUB),
            "-signature", str(SIG_FILE), str(BINARY),
        ])
        if not good or "Verified OK" not in (out + err):
            warn("Self-verify FAILED.  DO NOT UPLOAD THIS RELEASE.")
            print(out + err, file=sys.stderr)
            raise SystemExit(1)
        ok("Self-verify passed.")

        sha256 = hashlib.sha256(BINARY.read_bytes()).hexdigest()
        SHA_FILE.write_text(f"{sha256}  cripper\n", encoding="utf-8")
        ok(f"SHA-256: {sha256}")
        ok("Wrote cripper.sha256 -- publish on a SECOND channel.")

    except SystemExit:
        cleanup_on_fail(delete_binary=True)
        raise

    # 10. Cleanup
    for p in (PATCHED, TMP_PUB):
        try: p.unlink()
        except FileNotFoundError: pass

    print("\n" + "=" * 62)
    print(f"  LINUX BUILD COMPLETE  (v{version})")
    print("=" * 62)
    print(f"Next steps for v{version}:")
    print()
    print(f"  1. git tag -s v{version} && git push --tags")
    print(f"  2. GitHub -> Releases -> Draft new release")
    print(f"     Tag:    v{version}     <-- must match exactly")
    print("     Upload: cripper  cripper.sig  cripper.sha256")
    print("  3. Publish cripper.sha256 on a SECOND channel")
    print("     (your site, Matrix, Twitter)")
    print("  4. Verify a fresh download from the public URL:")
    print(f"     curl -LO https://github.com/{repo}/releases/latest/download/cripper")
    print("     ./cripper --verify-installed")
    print()
    print("NEVER upload private.pem.")
    print("=" * 62)


if __name__ == "__main__":
    main()
