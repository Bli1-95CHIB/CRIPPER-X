#!/usr/bin/env bash
# CRIPPER-X Secure Installer

set -e

REPO="Bli1-95CHIB/CRIPPER-X"
INSTALL_DIR="/usr/local/bin"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "[*] Downloading CRIPPER-X from GitHub..."
curl -sL "https://github.com/${REPO}/releases/latest/download/cripper" -o "$TMP_DIR/cripper"
curl -sL "https://github.com/${REPO}/releases/latest/download/cripper.sig" -o "$TMP_DIR/cripper.sig"
curl -sL "https://github.com/${REPO}/releases/latest/download/cripper.sha256" -o "$TMP_DIR/cripper.sha256"

echo "[*] Verifying SHA-256 checksum..."
cd "$TMP_DIR"
if ! sha256sum -c cripper.sha256 > /dev/null 2>&1; then
    echo "[!] Checksum verification FAILED. Aborting."
    exit 1
fi
echo "[+] Checksum OK."

chmod +x "$TMP_DIR/cripper"

echo "[*] Verifying RSA Signature..."
if ! "$TMP_DIR/cripper" --verify-installed "$TMP_DIR/cripper" > /dev/null 2>&1; then
    echo "[!] Signature verification FAILED. Aborting."
    exit 1
fi
echo "[+] Signature Valid."

echo "[*] Installing to ${INSTALL_DIR} (requires sudo)..."
sudo mv "$TMP_DIR/cripper" "${INSTALL_DIR}/cripper"
sudo chmod 755 "${INSTALL_DIR}/cripper"

echo "[+] CRIPPER-X installed successfully!"
echo "    Run 'cripper --help' to get started."
