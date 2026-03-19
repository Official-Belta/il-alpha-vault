# IL Alpha Vault — Competitive Analysis

Generated 2026-03-19 | CEO Review

---

## Market Position

Our "vol-based LP on/off toggle" has **no direct on-chain competitor**. Every existing protocol keeps LP active during high volatility — we are the only one that turns it off entirely.

---

## Competitor Overview

| Protocol | TVL | Fee | IL Strategy | Status |
|----------|-----|-----|-------------|--------|
| Arrakis | ~$1.8B (peak) | B2B negotiated | Vol↑ → raise fees (LP stays on) | Leading, V4 active |
| Gamma | ~$5M | Token-funded | Range adjustment (LP stays on) | Post-hack recovery |
| Bunni | DEAD | — | Dynamic curves + lending | Hacked $8.4M, shut down |
| Charm | Small | 5% of trade fees | Passive range rebalancing | Alive, no hacks |
| Sommelier | ~$15M | 1% mgmt + 10% perf | Portfolio-level hedging | Active |
| Maverick | ~$41M | AMM fees | Directional LP (user decides) | Active, own AMM |
| Yield Basis | New | veYB token | 2x leverage to cancel IL | Early stage |
| **IL Alpha** | **$0** | **10% perf + 0% mgmt** | **Vol↑ → LP fully removed** | **Phase 2 complete** |

---

## IL Defense Approaches Compared

```
                    What happens when volatility spikes?

Arrakis:     Raise swap fees (LP stays in pool)       → still exposed to IL
Gamma:       Widen range (LP stays in pool)            → still exposed to IL
Charm:       Rebalance range (LP stays in pool)        → still exposed to IL
Maverick:    LP decides manually                       → manual, expert-only
Yield Basis: Leverage cancels IL mathematically         → adds leverage risk
Sommelier:   Hedge entire portfolio                    → not LP-specific

IL Alpha:    Remove LP entirely                        → IL exposure = 0
```

---

## Detailed Competitor Profiles

### Arrakis Finance

- **TVL:** Peaked ~$1.8B, facilitated $20B+ cumulative volume. 100+ token issuers on Arrakis Pro.
- **V4 Status:** Already live. First whitelisted dynamic fee hook on Uniswap V4.
- **Strategy:** `beforeSwap` hook adjusts fees based on pool inventory balance and volatility. Higher vol → higher fees → arbitrage becomes unprofitable.
- **Target:** B2B — token issuers managing Protocol Owned Liquidity (POL).
- **Strengths:** First-mover on V4 dynamic fees, strong B2B pipeline, modular architecture.
- **Weaknesses:** B2B focus means retail LPs are underserved. No passive yield product.
- **Our gap:** Arrakis serves token issuers managing POL. We serve DAO treasuries seeking capital-preserved yield. Non-overlapping markets.

### Gamma Strategies

- **TVL:** ~$5M (down from much higher, post-hack). Deployed across 36 chains.
- **Hack:** $6.4M exploit (Jan 2024) — flash loan + misconfigured deposit proxy price thresholds.
- **Strategy:** MultiPosition Strategies — up to 20 different LP positions with different shapes. Automated rebalancing.
- **Fee:** GAMMA token stakers receive protocol fees. Revenue ~$22K/month.
- **Strengths:** Broad chain coverage, long track record (rebranded from Visor Finance).
- **Weaknesses:** Trust deficit post-hack. TVL collapsed. Token has limited utility.
- **Our gap:** Gamma optimizes ranges but never questions whether you should LP at all. Our binary on/off is simpler and more effective.

### Bunni (DEAD — Critical Lesson)

- **What happened:** $8.4M exploit (Sep 2025). Precision bug in BunniHook's liquidity accounting — attacker made 44 tiny withdrawals exploiting rounding errors. $2.4M lost on Ethereum, $5.9M on Unichain.
- **Why it died:** Founders stated they lacked 6-7 figures needed for audit/monitoring costs to relaunch.
- **Before death:** Most innovative V4 hook implementation. Achieved 100x more volume/TVL than non-hooked pools. Surpassed $1B volume.
- **Lesson for us:**
  1. Rounding errors in liquidity accounting are a real threat
  2. Exhaustive edge-case testing around deposit/withdrawal is critical
  3. Budget heavily for audits — minimum $50-150K
  4. Simpler design = smaller attack surface
- **Our opportunity:** The "leading V4 hook LP protocol" slot is vacant.

### Charm Finance / Alpha Vaults

- **TVL:** Small (low single-digit millions).
- **Fee:** No exit fees, no performance fees, no management fees. Only 5% of Uniswap fee income to treasury.
- **Strategy:** Passive rebalancing of concentrated liquidity ranges on V3.
- **Track record:** Longest-running LP vault without a major exploit.
- **Strengths:** Simplicity, longevity, extremely LP-friendly fees.
- **Weaknesses:** Very small scale, no V4 strategy, no growth incentives.
- **Our lesson:** Simple design + low fees = survival. Charm is the cockroach of LP vaults.

### Sommelier Finance

- **TVL:** ~$15M direct, but infrastructure powers larger protocols ($3B+ through Spark/Veda).
- **Fee:** 1% management + 10% performance. Fees auctioned for SOMM token → ~20% staking yield.
- **Strategy:** ERC-4626 "Cellars" curated by external strategists. Can shift entirely to stablecoins during crashes.
- **Strengths:** Governance-curated strategies, infrastructure play is higher leverage.
- **Weaknesses:** Complex architecture (Cosmos bridge), TVL declined from ~$100M peak.
- **Our gap:** General-purpose vaults, not LP-specific. No concentrated liquidity IL management.

### Maverick Protocol

- **TVL:** ~$41M. $32B cumulative volume. 4,000%+ capital efficiency for stablecoin pools.
- **Strategy:** Dynamic Distribution AMM — LPs express price direction beliefs. Correct bet → IL=0. Wrong bet → 2x IL.
- **Backed by:** Binance, Coinbase ($9M raise).
- **Strengths:** Exceptional capital efficiency, genuinely innovative AMM design.
- **Weaknesses:** Requires directional conviction (not passive), own AMM (not Uniswap ecosystem).
- **Our gap:** Maverick is manual; we automate the decision. We serve passive LPs.

### Yield Basis (by Curve founder Michael Egorov)

- **Strategy:** 2x leverage on LP positions to mathematically eliminate IL.
- **Volume:** $1.63B processed in 2025. Expanding from BTC/ETH to tokenized RWAs.
- **Risk:** Leverage adds liquidation risk. Different risk profile than our approach.
- **Our differentiation:** No leverage. We avoid IL by stepping out, not by doubling down.

---

## Hack History — Lessons

| Protocol | Date | Loss | Root Cause | Our Defense |
|----------|------|------|------------|-------------|
| Bunni V2 | Sep 2025 | $8.4M | Rounding error in hook accounting | Fuzz tests + virtual shares |
| Gamma | Jan 2024 | $6.4M | Deposit proxy misconfiguration | DepositTooSmall + setPoolKey validation |
| Cetus | May 2025 | $223M | Spoofed tokens + pricing flaw | Currency validation in setPoolKey |
| GMX V1 | Jul 2025 | $42M | Reentrancy in GLP pools | nonReentrant modifier |

Pattern: 80.5% of funds lost in 2024-2025 from access control / parameter validation failures.

---

## V4 Hook Ecosystem (March 2026)

- V4 launched January 30, 2025
- ~5,000 hooks initialized, $190B+ cumulative volume
- V4 TVL crossed $1B in July 2025
- 1,375 Hook Incubator applications, 241+ hooks shipped, 700+ developers onboarded
- Adoption: gradual. V3 → V4 migration is slow. Expected to become standard by late 2026.

---

## Strategic Implications

### 1. The "V4 Hook LP Leader" Slot Is Vacant

Bunni was the leader and died. Nobody has claimed this position. First credible protocol with a strong audit fills it.

### 2. DAO Treasury Gap Is Wide Open

Arrakis owns B2B for token issuers (Protocol Owned Liquidity). Nobody owns B2B for DAO treasuries seeking capital preservation. $24.5B in DAO treasuries, 67% idle — because LP means IL risk that governance won't approve. We fill that gap: LP-level returns (15%+) with treasury-grade risk (Sharpe 3.66, Max DD -12%).

### 3. Idle Capital Is a Differentiator Opportunity (Phase 5-6)

When LP is "off," capital sits idle. Routing idle funds to Aave/Compound for lending yield during off periods would add 3-5% base APY. No competitor does this.

### 4. Audit Budget Is Non-Negotiable

Bunni died because they couldn't afford $150-700K for audit + monitoring. Budget minimum $50-150K. This is not optional.

### 5. Simplicity Is a Moat

```
Bunni (complex) → died
Gamma (complex) → hacked
Charm (simple)  → survived 3+ years, zero hacks

Our design is intentionally simple:
  - One hook, one vault
  - One decision: LP on or LP off
  - EWMA vol oracle (proven math, no ML black box)
```

---

## DAO Treasury Competitive Landscape

What DAOs currently do with idle capital — and why each fails:

| Option | Yield | Risk | Why DAOs Use It | Why It's Not Enough |
|--------|-------|------|-----------------|---------------------|
| Hold stablecoins | 0% | None | Default, requires no governance vote | $16.4B earning nothing |
| Aave/Compound | 4-5% | Low | Simple, well-audited | Too slow for treasury growth |
| Lido/stETH | 6-8% | Medium | ETH yield, liquid | ETH-denominated, ETH price risk |
| Raw LP (Uniswap) | 15-30% | High | Highest yield | 49.5% of LPs lose money, -45% Max DD |
| Market makers | Variable | Medium | Professional management | $10-50K/mo, unaffordable for most |
| **IL Alpha Vault** | **15%+** | **Low-Med** | **LP yield + capital preservation** | **Best risk-adjusted option** |

### Why IL Alpha Wins for DAO Treasuries

```
Governance cares about:
  1. Downside protection  → Max DD -12% (vs -45% raw LP)
  2. Risk-adjusted return  → Sharpe 3.66 (vs S&P 500 ~0.5)
  3. Exit flexibility      → ERC-4626, no lockup
  4. Cost transparency     → Performance-fee-only (0% when losing)
  5. Auditability          → Open source, on-chain event logs

No existing LP manager frames their product for governance votes.
We do.
```

---

## Positioning Statement

### Important: What we compete with and what we don't

```
NOT our competition:          WHY:
  Aave (4-5% lending)          Different category. Lending ≠ LP.
  Lido/EtherFi (4-8% staking)  Different category. Staking ≠ LP.

  → If someone just wants yield on ETH, tell them to use Lido.
  → We only win when the customer wants LP-level returns (15%+).

OUR competition:
  Arrakis, Gamma, Charm        LP management protocols.
  "Do nothing" (manual LP)     49.5% of LPs lose money doing this.
  Market makers (Wintermute)   B2B only, $10-50K/mo, unaffordable for most.
```

### Positioning for new token projects

```
❌ WRONG: "We supply your pool's liquidity"
   → We pull out during high vol. This is a broken promise.

✅ RIGHT: "Your treasury is melting from IL. We slow the burn 3x."
   → Treasury survives 12+ months instead of 6.
   → Long-term liquidity > short-term liquidity guarantee.
```

---

## Positioning Statement

> IL Alpha Vault is the first V4 hook vault designed for DAO treasury capital preservation. While competitors keep LP active during volatility — exposing treasuries to impermanent loss — we remove exposure entirely. Sharpe 3.66, Max DD -12%, performance-fee-only, ERC-4626 standard. Treasury-grade risk management for LP-level returns.
