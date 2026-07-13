# Token-Bound Executable Skills — Reference Implementation

Reference implementation, deterministic toolchain, and frozen test vectors for the ERC draft
**"Token-Bound Executable Skills"** (KERNEL v4.3, specification frozen).

An ERC-721 extension that binds a token to a hash-verifiable executable skill package:
the chain anchors *exactly which bytes, package version, and publication history* a token
commits to; any runtime (including LLM agent runtimes) can fetch the package from anywhere,
verify it byte-for-byte against the on-chain anchors, and execute it.

```
ERC-721 layer          who owns this skill token
Skill Binding layer    mdHash / packageHash / version / packageURI / updateAuthority / frozen
On-chain Document      optional plaintext primary document, readable from the chain itself
Skill Object Model     deterministic DAG-CBOR object graph, per-file CIDs (off-chain, normative)
```

## Status (2026-07-11)

- Specification: **KERNEL v4.3 — frozen**
- Foundry test suite: **12/12 PASS** (every MUST clause of the frozen spec as an assertion)
- Interface IDs (compiler-verified):
  `ISkillToken = 0x734553a6` · `IOnchainSkillDocument = 0x7050dd2c`
- Six frozen test vectors reproduced byte-for-byte across five independent machines
- End-to-end closed on local chains **and on the Sepolia public testnet** (see Deployments):
  the verifier consumed anchors **read back from the chain**, not from local files

## Deployments

| Network | Contract | Token #1 |
|---|---|---|
| Sepolia | [`0x12cc1a5319c6F08bFB50982e3814A376A59fE550`](https://sepolia.etherscan.io/address/0x12cc1a5319c6F08bFB50982e3814A376A59fE550) | the `public-v1` frozen sample vector |

Mint tx [`0x3d4f0d6f…d599a36`](https://sepolia.etherscan.io/tx/0x3d4f0d6ffccc9f788cee09283d50c4e765905628b592c5b3a72081e34d599a36)
(block 11261685). The genesis `SkillUpdated` event carries `mdHash ‖ packageHash ‖ version`
verbatim in its data field: the skill's fingerprints are part of public chain history.

Read the anchors yourself — no local setup needed beyond `cast`:

```bash
cast call 0x12cc1a5319c6F08bFB50982e3814A376A59fE550 \
  "skillOf(uint256)((bytes32,bytes32,uint64))" 1 \
  --rpc-url https://ethereum-sepolia-rpc.publicnode.com
# returns (mdHash, packageHash, version); compare with vectors/public-v1/vector.json
```

Then verify the real package bytes against what the chain returned:

```bash
python3 tools/skill-pack/verify.py vectors/public-v1 \
  --mdhash <first value> --packagehash <second value>
```

## Repository layout

```
contracts/               SkillToken.sol + ISkillToken / IOnchainSkillDocument (spec 1:1)
test/                    Foundry suite (12 tests, one per MUST clause)
tools/skill-pack/        pack.py (canonical packer) / verify.py (agent-side verifier)
                         / som.py (deterministic DAG-CBOR + CID library, zero deps)
vectors/                 six frozen test vectors + path-negative-tests.json
                         (KEY.demo files are NON-CRYPTOGRAPHIC TEST keys)
schemas/                 manifest + confidentiality descriptor JSON Schemas
scripts/ec2_e2e.sh       build -> test -> deploy -> mint -> verify-from-chain
vectors-objects-bundle.tar.gz   insurance copy of all vectors/*/objects/
```

## Quick start (EC2 / Linux, the exact proven path)

```bash
# 0) clone fresh
git clone https://github.com/garyyang-finchip/skill-token-standard.git
cd skill-token-standard

# 1) hygiene: strip CRLF (Windows transit) and restore objects if transport dropped them
find . \( -name '*.sh' -o -name '*.py' \) -exec sed -i 's/\r$//' {} +
ls vectors/public-v1/objects >/dev/null 2>&1 || tar -xzf vectors-objects-bundle.tar.gz

# 2) offline verification (no chain needed) — proves the deterministic toolchain
MD=$(python3 -c "import json;print(json.load(open('vectors/public-v1/vector.json'))['mdHash'])")
PKG=$(python3 -c "import json;print(json.load(open('vectors/public-v1/vector.json'))['packageHash'])")
python3 tools/skill-pack/verify.py vectors/public-v1 --mdhash $MD --packagehash $PKG
# expected: 7x [OK] ... PASS - package verified; safe to hand to sandboxed runtime.

# 3) Foundry: compile + full MUST-clause test suite
curl -L https://foundry.paradigm.xyz | bash && source ~/.bashrc && foundryup
forge install foundry-rs/forge-std --no-git
forge build
forge test -vvv
# expected: 12 tests passed, 0 failed

# 4) local chain (ganache; anvil needs GLIBC >= 2.35 — see Troubleshooting)
npm install -g ganache
nohup ganache --wallet.mnemonic "test test test test test test test test test test test junk" \
  --chain.chainId 31337 > /tmp/ganache.log 2>&1 &
sleep 4 && cast chain-id   # expected: 31337

# 5) deploy + mint the real frozen skill as token #1
PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
ADDR=$(cast wallet address $PK)
DEPLOY=$(forge create --broadcast --private-key $PK --json \
  contracts/SkillToken.sol:SkillToken --constructor-args "Skill Token" "SKILL")
CONTRACT=$(echo "$DEPLOY" | python3 -c "import json,sys;print(json.load(sys.stdin)['deployedTo'])")
echo "SkillToken deployed: $CONTRACT"
cast send $CONTRACT "mintSkill(address,address,bytes32,bytes32,string)" \
  $ADDR $ADDR $MD $PKG "ipfs://public-v1" --private-key $PK > /dev/null
echo "Minted skill token #1"

# 6) the closing loop: read anchors FROM THE CHAIN, verify the package against them
CHAIN=$(cast call $CONTRACT "skillOf(uint256)((bytes32,bytes32,uint64))" 1)
CHAIN_MD=$(echo $CHAIN | tr -d '() ' | cut -d',' -f1)
CHAIN_PKG=$(echo $CHAIN | tr -d '() ' | cut -d',' -f2)
python3 tools/skill-pack/verify.py vectors/public-v1 --mdhash $CHAIN_MD --packagehash $CHAIN_PKG \
  && echo "END-TO-END PASS: on-chain anchors verified the real package byte-for-byte."
```

Or run everything at once: `bash scripts/ec2_e2e.sh` (auto-falls back to ganache when anvil
is unavailable).

## Reproducing the vectors

Two independent implementations MUST reproduce `vectors/*/skillroot.cbor` byte-for-byte.

```bash
python3 tools/skill-pack/pack.py <skill-dir> --out out/ \
    [--primary docs/agent.md] [--version N --prev 0x<previous-packageHash>] \
    [--encrypt path1,path2 --key <hex>]
python3 tools/skill-pack/verify.py out/ --mdhash 0x.. --packagehash 0x.. \
    [--version N --previous-packagehash 0x..] [--key <hex>]
```

The verifier enforces: packageHash, canonical re-encode byte-equality, closed-map schema +
path rules, the version chain (`digest(prev) == previous packageHash`), confidentiality
descriptor cross-matching against SkillRoot links, per-leaf digests, plaintext `mdHash`,
and strict UTF-8 on the primary document.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `\r: command not found` or similar | step 1 CRLF strip |
| `FileNotFoundError: vectors/.../objects/...` | `tar -xzf vectors-objects-bundle.tar.gz` |
| `anvil: GLIBC_2.35 not found` | use ganache (step 4) — same mnemonic, same keys |
| `Constructor argument count mismatch` | `--constructor-args` is greedy in current forge; it must be the **last** flag |
| `forge create` deploys nothing | add `--broadcast` (dry-run by default in current forge) |
| port 8545 in use | `pkill anvil; pkill -f ganache` and retry |

## License

Specification and reference code released under [CC0](LICENSE).
Test vectors embed a real-world sample skill package (MIT) as sample content.
`x-test-sha256-xor-stream-v1` is a NON-CRYPTOGRAPHIC TEST profile — never use it in production.
