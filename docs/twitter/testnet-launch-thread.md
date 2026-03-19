# Testnet Launch Thread — IL Alpha Vault

**Status:** Ready to post
**Format:** 7-tweet thread
**Target:** Crypto Twitter — DeFi LPs, builders, V4 devs

---

## Tweet 1 (Hook)

We just deployed IL Alpha Vault to Ethereum Sepolia.

The first Uniswap V4 hook that removes your LP when volatility spikes — before impermanent loss hits.

Not "widen the range." Not "raise fees."
We pull your liquidity entirely.

Here's what we shipped 🧵

---

## Tweet 2 (Backtest)

1/ Started with 6 months of real ETH/USDC data (Sep 2025 – Mar 2026).

Full bull → full bear cycle.

Result: our vol-based LP on/off signal outperformed both "always LP" and "just HODL."

99 Python tests. Thesis validated before writing a single line of Solidity.

---

## Tweet 3 (Contracts)

2/ Then we built the contracts.

• Uniswap V4 hook (afterSwap volatility check)
• ERC-4626 vault (deposit ETH, get shares)
• 2 control vaults: AlwaysLP + HODL
• 65 Solidity tests. 0 failures. Fuzz included.

Every LP manager keeps you in the pool during high vol.
We're the only one that takes you out.

---

## Tweet 4 (Deployment)

3/ Deployed to Sepolia. Verify everything on-chain:

✅ ILAlphaHook — sepolia.etherscan.io/address/0xb3150d39893dc6842bd4c0eb6d0fdab4a6211040
✅ ILAlphaVault — sepolia.etherscan.io/address/0x8a4a048e5da48de8dca28686a2d326048796e4b1
✅ AlwaysLPVault — sepolia.etherscan.io/address/0x7f6699ecb6cf92e385fa919fe2810f79b5c52040
✅ HODLVault — sepolia.etherscan.io/address/0x979c2460b29c0e8992fed8a3ba0a4284b2a10c0c

3 vaults. Same funding. Same pool.
Now we measure who wins.

---

## Tweet 5 (Keeper)

4/ The keeper bot is live.

Every cycle it:
→ Pushes volume estimates to the vol oracle
→ Checks if variance exceeds threshold
→ Triggers LP removal or re-entry

Fully automated. No manual management.
Your liquidity protects itself.

---

## Tweet 6 (Positioning)

5/ Every LP manager out there does the same thing when vol spikes:

Arrakis → raise fees (you're still in)
Gamma → widen range (you're still in)
Charm → rebalance (you're still in)

IL Alpha → remove LP entirely (exposure = 0)

If staying in the pool loses money, why stay?

---

## Tweet 7 (Next)

6/ What's next:

→ Monitor testnet across vol regimes
→ Compare ILAlpha vs AlwaysLP vs HODL with real data
→ Publish results publicly
→ External audit → Mainnet

Building in public. Everything verifiable on-chain.

Follow along.
