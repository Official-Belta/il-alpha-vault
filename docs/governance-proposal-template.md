# [DAO Name] Treasury Proposal: Allocate $[X]M to IL Alpha Vault

**Author:** IL Alpha Team
**Date:** [DATE]
**Status:** Draft
**Forum Discussion:** [LINK]

---

## TL;DR

Allocate $[X]M ([Y]% of idle treasury) to IL Alpha Vault to earn LP-level yields (15%+ APR) with institutional-grade risk management. Performance-fee-only — if the vault doesn't profit, [DAO Name] pays nothing.

---

## Motivation

[DAO Name] treasury currently holds ~$[TOTAL]M, of which ~$[IDLE]M sits idle in stablecoins/ETH earning 0% yield.

**Current treasury alternatives and their limitations:**

| Option | APR | Risk | Issue |
|--------|-----|------|-------|
| Hold stablecoins | 0% | None | Capital inefficiency |
| Aave/Compound | 4-5% | Low | Too slow for treasury growth |
| Lido/stETH | 6-8% | Medium | ETH-denominated, price risk |
| Direct LP (Uniswap) | 15-30% | High | 49.5% of LPs lose money |
| **IL Alpha Vault** | **15%+** | **Low-Med** | **Sharpe 3.66, Max DD -12%** |

---

## What is IL Alpha Vault?

A Uniswap V4 Hook-based vault that **automatically removes LP positions when impermanent loss risk exceeds fee income**. Unlike all other LP managers (Arrakis, Gamma, Charm) which keep LP active during volatility, IL Alpha turns LP off entirely — reducing IL exposure to zero during dangerous periods.

**Core mechanism:**
1. On-chain EWMA volatility oracle tracks market conditions
2. When `fee_yield > IL_cost` → LP is active (earning fees)
3. When `fee_yield < IL_cost` → LP is removed (capital preserved)
4. Binary decision, 24-hour cooldown, fully automated

---

## Risk Metrics (2-Year Backtest)

| Metric | IL Alpha | Always LP | HODL |
|--------|----------|-----------|------|
| **Sharpe Ratio** | **3.66** | 3.24 | 1.11 |
| **Max Drawdown** | **-12%** | -45% | -65% |
| Cumulative Return | +231% | +297% | +91% |
| Capital Preserved (worst case) | **88%** | 55% | 35% |

> S&P 500 Sharpe Ratio ~0.5. IL Alpha achieves 7x that.

**Testnet validation:** Three vaults (IL Alpha, AlwaysLP, HODL) running head-to-head on Ethereum Sepolia with identical conditions. [Live dashboard: LINK]

---

## Proposed Allocation

| Parameter | Value |
|-----------|-------|
| Amount | $[X]M USDC |
| % of treasury | [Y]% |
| Target pool | [ETH/USDC / wstETH/ETH] |
| Fee structure | 10% performance fee, 0% management fee |
| Lockup | None (ERC-4626, instant withdrawal) |
| Monitoring period | 4 weeks before full evaluation |

---

## Fee Structure

- **Performance fee:** 10% of profits only
- **Management fee:** 0%
- **Deposit/withdrawal fee:** 0%
- **If vault loses money:** Fee = $0

This is the lowest fee tier in the LP management category:

| Protocol | Perf. Fee | Mgmt. Fee |
|----------|-----------|-----------|
| Yearn v3 | 10% | 2% |
| Sommelier | 10-20% | 2% |
| Arrakis | 10% | 1% |
| **IL Alpha (Stage 1)** | **10%** | **0%** |

---

## Risk Analysis

### Smart Contract Risk
- Open-source code: [GitHub LINK]
- Virtual shares implementation (prevents ERC-4626 inflation attacks)
- Reentrancy protection on all state-changing functions
- Security audit: [STATUS — planned/completed, firm name]
- Testnet operation since [DATE] with zero incidents

### Keeper Dependency
- Automated keeper bot updates volatility and triggers rebalancing
- Public `rebalance()` function — anyone can call as fallback
- Keeper failure = vault holds position (fails safe, not fails dangerous)

### Strategy Risk
- In strong bull markets, AlwaysLP outperforms on raw returns (+297% vs +231%)
- IL Alpha optimizes for **risk-adjusted returns**, not maximum returns
- Best suited for treasury capital where capital preservation > return maximization

### Exit Strategy
- ERC-4626 standard vault
- `redeem()` for instant withdrawal, no lockup
- If LP is active, vault automatically removes liquidity before returning assets
- `emergencyWithdraw()` available to vault owner

---

## Implementation Timeline

| Week | Action |
|------|--------|
| Week 1 | Governance vote passes |
| Week 2 | Treasury multisig deposits $[X]M to IL Alpha Vault |
| Week 3-6 | 4-week monitoring period |
| Week 7 | Performance report published to governance forum |
| Week 8+ | Continue or withdraw based on results |

---

## Success Criteria (4-week evaluation)

- [ ] Vault operational with zero downtime
- [ ] Sharpe ratio > 2.0 (annualized)
- [ ] Max drawdown < 15%
- [ ] All keeper cycles executed on time
- [ ] Transparent reporting published weekly

---

## About IL Alpha

- Uniswap V4 Hook-based protocol
- Phase 3 (Testnet Validation) complete
- 65 Solidity tests, 99 Python backtest tests — all passing
- Contracts deployed on Ethereum Sepolia since [DATE]
- [Link to milestone site]
- [Link to GitHub]
- [Link to testnet dashboard]

---

## Vote

- **FOR:** Allocate $[X]M to IL Alpha Vault for 4-week trial
- **AGAINST:** Do not allocate
- **ABSTAIN**

---

*This proposal was prepared by the IL Alpha team. All data is from backtests and testnet — not guaranteed. [DAO Name] governance retains full control over treasury assets via ERC-4626 instant withdrawal.*
