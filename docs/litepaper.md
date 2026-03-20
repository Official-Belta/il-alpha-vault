# IL Alpha — Litepaper

**Treasury-grade LP management on Uniswap V4**

v1.0 | March 2026

---

## 1. Problem

### LP is broken for institutional capital

Uniswap concentrated liquidity offers 15-30% APR — but 49.5% of LPs lose more to impermanent loss (IL) than they earn in fees. The net result across V3 LPs: **-$61M** (fees $199M minus IL $260M).

This creates a paradox: the highest-yield opportunity in DeFi is also the one most likely to lose money.

**The consequence:** $24.5B in DAO treasury capital sits idle. 67% of DAO treasuries earn 0% because governance cannot approve a strategy where half the participants lose money. Treasury managers are stuck between Aave's safe 4% and LP's dangerous 15%+.

| Alternative | Yield | Risk | Problem |
|-------------|-------|------|---------|
| Hold stablecoins | 0% | None | Capital inefficiency |
| Aave/Compound | 4-5% | Low | Too slow for treasury growth |
| Lido/stETH | 6-8% | Medium | ETH price exposure |
| Direct LP (Uniswap) | 15-30% | High | 49.5% lose money, -45% max drawdown |

The missing option: LP-level returns with treasury-grade risk.

---

## 2. Insight

### Impermanent loss is negative gamma exposure

A concentrated LP position is economically equivalent to selling options. The LP earns a premium (swap fees) but faces negative gamma — when price moves, the position loses value faster than it earns fees.

The expected value of an LP position at any moment:

```
EV = fee_yield - IL_cost
   = (pool_fee × volume) - (0.5 × σ² × concentration × position_value)
```

Where:
- `fee_yield` = pool fee rate × swap volume flowing through the position
- `IL_cost` = gamma exposure × realized variance (from options pricing theory)
- `σ²` = annualized variance of the price process

**When EV > 0:** LP is profitable. Fees exceed IL.
**When EV < 0:** LP is value-destructive. IL exceeds fees.

The insight: **you can measure this in real-time.** Volatility is observable. Fee income is observable. The decision to LP or not is computable.

---

## 3. Solution

### Binary LP toggle based on real-time EV

IL Alpha is a Uniswap V4 hook that makes one decision:

```
If fee_yield > IL_cost → LP active (earn fees)
If fee_yield < IL_cost → LP removed entirely (preserve capital)
```

**Why binary?** Every existing LP manager (Arrakis, Gamma, Charm) keeps LP active during high volatility — adjusting ranges or fees. They reduce IL but never eliminate it. IL Alpha removes LP entirely when EV is negative, reducing IL exposure to zero during dangerous periods.

**Why this works for treasuries:** The strategy sacrifices some upside (+231% vs +297% for always-on LP) for dramatically less downside (-12% max drawdown vs -45%). This is the exact tradeoff that governance votes require.

---

## 4. Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Uniswap V4 │◄────│ ILAlphaHook  │────►│    Keeper     │
│  PoolManager│     │ (afterSwap)  │     │  (1hr cycle)  │
│  Singleton  │     │ EWMA Oracle  │     │               │
└──────┬──────┘     └──────┬───────┘     └───────────────┘
       │                   │
       │            ┌──────▼───────┐
       └────────────│ ILAlphaVault │
                    │  (ERC-4626)  │
                    └──────────────┘
```

### ILAlphaHook (V4 Hook)

Attached to Uniswap V4 pools via the `afterSwap` callback. On every swap:

1. **Update EWMA variance oracle.** Computes squared tick deltas, applies exponential weighting (λ = 0.94, ~24hr half-life), normalizes to hourly.

2. **Update volume EWMA.** Tracks swap volume with same decay factor for fee yield estimation.

3. **Check volume spike.** If single swap > 3× ewmaVolume, trigger emergency LP removal (bypasses cooldown).

4. **Evaluate LP toggle.** Compare fee yield vs IL cost. If state should change and 24-hour cooldown has elapsed, toggle LP active/inactive.

The keeper bot blends off-chain volatility data (from Binance) with the on-chain estimate at 50% weight, providing a more responsive signal while maintaining on-chain verifiability.

### ILAlphaVault (ERC-4626)

Standard tokenized vault with:

- **Real-time LP valuation.** `totalAssets()` computes position value from current pool tick using `LiquidityAmounts`, not stale accounting. (Lesson from Gamma's $6.4M hack.)

- **TWAP manipulation check.** Deposit and withdraw compare spot tick against oracle tick. Reverts if deviation > ±500 ticks (~5%).

- **Virtual shares.** 1e6 virtual shares and assets prevent first-depositor inflation attacks.

- **Public rebalance.** Anyone can call `rebalance()` — no single point of failure if keeper goes offline.

---

## 5. Backtest Results

2-year real ETH/USDC price data (January 2024 — March 2026), covering bull and bear regimes.

| Metric | IL Alpha | AlwaysLP | HODL |
|--------|----------|----------|------|
| **Sharpe Ratio** | **3.66** | 3.24 | 1.11 |
| **Max Drawdown** | **-12%** | -45% | -65% |
| Cumulative Return | +231% | +297% | +91% |
| Capital Preserved (worst case) | 88% | 55% | 35% |

IL Alpha sacrifices 22% raw return for **73% reduction in worst-case drawdown**.

For a $5M DAO treasury allocation:

| | Always LP worst case | IL Alpha worst case |
|---|---|---|
| Loss | **-$2.25M** | **-$600K** |

Same fees in calm. 75% less loss in storms.

---

## 6. Security

### Design philosophy: simplicity as security

```
Bunni V2: rehypothecation + shapeshifting + dynamic curves → $8.4M hack → dead
Gamma:    complex multi-position management → $6.4M hack → TVL collapsed
Charm:    simple passive rebalancing → 3 years, zero hacks → alive

IL Alpha: one hook, one vault, one decision (LP on or LP off)
```

### Defenses

| Layer | Mechanism |
|-------|-----------|
| Share pricing | Real-time LP valuation via pool tick (not stale) |
| Manipulation | TWAP check on deposit/withdraw (±500 tick threshold) |
| Inflation attack | Virtual shares (1e6 offset) |
| Emergency | Volume spike trigger bypasses 24hr cooldown |
| Redundancy | Public `rebalance()` — anyone can call |
| Audit | 4-round internal security audit: 0 Critical, 0 High |

**Status:** Seeking professional audit via UFSF (Uniswap Foundation Security Fund).

---

## 7. Fee Model

```
Stage 1 (TVL < $5M):   10% performance fee, 0% management, 0% withdrawal
Stage 2 (TVL $5-20M):  15% performance fee, 0.5% management
Stage 3 (TVL $20M+):   15-20% performance fee, 1% management
```

**If the vault doesn't profit, you pay nothing.** Performance-fee-only at launch — lowest cost in the LP management category.

| Protocol | Perf. Fee | Mgmt. Fee |
|----------|-----------|-----------|
| Yearn v3 | 10% | 2% |
| Sommelier | 10-20% | 2% |
| Arrakis | 10% | 1% |
| **IL Alpha** | **10%** | **0%** |

---

## 8. Roadmap

```
Phase 1-3  ████████████████  COMPLETE
  Backtest (99 tests) → Contracts (65 tests) → Testnet + 4-round audit

Phase 4    ████              IN PROGRESS
  Base mainnet deployment, $1.2K seed, 4-week live validation

Phase 5    ░░░░              NEXT
  UFSF audit subsidy → professional audit → deposit cap open

Phase 6    ░░░░░░░░
  DAO treasury partnerships (target: 3-5 DAOs, $1-2M each)

Phase 7+   ░░░░░░░░░░░░
  Rehypothecation (idle capital → Aave), multi-chain, governance
```

---

## 9. Links

- **Site:** https://official-belta.github.io/il-alpha-site/
- **Thesis:** https://official-belta.github.io/il-alpha-site/thesis.html
- **GitHub:** https://github.com/Official-Belta/il-alpha-vault
- **Contracts (Base):** [pending deployment]

---

## 10. Conclusion

IL Alpha answers one question: **should this capital be LP right now?**

When fees exceed IL cost, the vault earns. When they don't, the vault protects. No range adjustment, no leverage, no rehypothecation — just a binary decision backed by options pricing math and on-chain volatility data.

For DAO treasuries choosing between Aave's 4% and LP's risky 15%, IL Alpha offers a third option: **LP-level returns with treasury-grade risk.**

Sharpe 3.66. Max Drawdown -12%. Performance-fee-only.

---

*This document is for informational purposes only. Backtest results do not guarantee future performance. Smart contracts are unaudited by a professional firm. Use at your own risk.*
