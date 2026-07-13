# Token-Bound Executable Skills — Reference Implementation (KERNEL v4.3)

Reference implementation, deterministic toolchain, and frozen test vectors for
the ERC draft "Token-Bound Executable Skills" (KERNEL v4.3, spec frozen).

Milestone M1 (2026-07-11): 12/12 Foundry tests pass; first on-chain deployment
and mint (Skill Token #1 = finchip-daily-finance-brief v0.3.1); chain-anchor ->
package verification closed end-to-end.
Interface IDs (compiler-verified): ISkillToken 0x734553a6, IOnchainSkillDocument 0x7050dd2c.

## Layout
- contracts/            SkillToken.sol + interfaces (spec 1:1)
- test/                 Foundry suite: every MUST clause as an assertion (12 tests)
- tools/skill-pack/     pack.py / verify.py / som.py (zero-dependency, Python 3.9+)
- vectors/              six frozen vectors + path-negative-tests.json (KEY.demo = TEST ONLY)
- schemas/              manifest + confidentiality JSON Schemas
- scripts/ec2_e2e.sh    build -> test -> deploy -> mint -> verify-from-chain
- vectors-objects-bundle.tar.gz  insurance: if vectors/*/objects/ got lost in
  transport, run: tar -xzf vectors-objects-bundle.tar.gz

## Quick start
    find . \( -name '*.sh' -o -name '*.py' \) -exec sed -i 's/\r$//' {} +   # CRLF guard
    ls vectors/public-v1/objects >/dev/null 2>&1 || tar -xzf vectors-objects-bundle.tar.gz
    bash scripts/ec2_e2e.sh

Notes: anvil needs GLIBC >= 2.35; the script auto-falls back to ganache
(same test mnemonic, same keys). forge create uses --broadcast with
--constructor-args placed last (greedy flag in current forge).
