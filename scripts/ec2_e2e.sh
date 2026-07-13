#!/usr/bin/env bash
# Token-Bound Executable Skills — EC2 end-to-end (KERNEL v4.3)
# Gate 1: build+tests. Gate 2: local chain mint of the real frozen skill.
set -euo pipefail
cd "$(dirname "$0")/.."

# ---- Gate 0: toolchain ----
command -v forge >/dev/null || { curl -L https://foundry.paradigm.xyz | bash; ~/.foundry/bin/foundryup; export PATH="$HOME/.foundry/bin:$PATH"; }
[ -d lib/forge-std ] || forge install foundry-rs/forge-std --no-git

# ---- Gate 1: compile + full MUST-clause test suite ----
forge build
forge test -vvv

# ---- Gate 2: anvil + mint the real frozen skill (public-v1 vector) ----
if anvil --version >/dev/null 2>&1; then
  anvil --silent & NODE=$!; sleep 2
else
  echo "anvil unavailable (glibc?); falling back to ganache"
  command -v ganache >/dev/null || npm install -g ganache
  nohup ganache --wallet.mnemonic "test test test test test test test test test test test junk" \
    --chain.chainId 31337 > /tmp/ganache.log 2>&1 & NODE=$!; sleep 4
fi
PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80  # anvil[0]
ADDR=$(cast wallet address $PK)
# NOTE: --constructor-args is greedy in current forge; it must come LAST
DEPLOY=$(forge create --broadcast --private-key $PK --json \
  contracts/SkillToken.sol:SkillToken --constructor-args "Skill Token" "SKILL")
CONTRACT=$(echo "$DEPLOY" | python3 -c "import json,sys;print(json.load(sys.stdin)['deployedTo'])")
echo "SkillToken deployed: $CONTRACT"

MD=0x3ffb913330b04a8ec121fa218cc9dcc8916bc10aaf88a5b58aefb331c1c3015f
PKG=$(python3 -c "import json;print(json.load(open('vectors/public-v1/vector.json'))['packageHash'])")
cast send $CONTRACT "mintSkill(address,address,bytes32,bytes32,string)" \
  $ADDR $ADDR $MD $PKG "ipfs://public-v1" --private-key $PK > /dev/null
echo "Minted skill token #1  (finchip-daily-finance-brief v0.3.1)"

# ---- Gate 3: read chain -> verify package exactly as an agent would ----
CHAIN_MD=$(cast call $CONTRACT "skillOf(uint256)((bytes32,bytes32,uint64))" 1 | tr -d '()' | cut -d',' -f1)
CHAIN_PKG=$(cast call $CONTRACT "skillOf(uint256)((bytes32,bytes32,uint64))" 1 | tr -d '()' | cut -d',' -f2 | tr -d ' ')
python3 tools/skill-pack/verify.py vectors/public-v1 --mdhash $CHAIN_MD --packagehash $CHAIN_PKG
echo "END-TO-END PASS: on-chain anchors verified the real package byte-for-byte."
kill $NODE
