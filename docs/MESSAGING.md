# IL Alpha Vault — Messaging & Positioning Guide

Generated from CEO strategy session 2026-03-19.
Updated 2026-03-20: B2B pivot — DAO treasury as primary target.

---

## One-Liner

> "Uniswap V4 hook that protects DAO treasury capital from impermanent loss. LP fees with institutional-grade risk management."

---

## What We Are / Are NOT

### We are NOT:
- **NOT a staking alternative.** Lido/EtherFi give 4-8%. If someone just wants ETH yield, tell them to use those.
- **NOT a lending alternative.** Aave gives 4-5% on stablecoins. Different category.
- **NOT a liquidity guarantee.** We pull LP during high volatility. Don't promise "always-on liquidity."
- **NOT Protocol Owned Liquidity management.** That's Arrakis. We protect treasury capital, not manage token liquidity.

### We ARE:
- **Treasury-grade LP management** for capital that needs LP-level returns (15%+) with capital preservation
- For DAO treasuries and institutional capital that can't afford 45% drawdowns
- Automatic: deposit once, vault handles everything. ERC-4626 standard, no lockup.

### Our competition:
- Arrakis, Gamma, Charm (LP management protocols — all keep LP on during vol)
- "Do nothing" / hold stablecoins (67% of DAO treasuries sit idle at 0% yield)
- Aave (4%), Lido (6-8%) — lower returns but safer → we compete on risk-adjusted basis
- Market makers (Wintermute) — $10-50K/mo, unaffordable for most DAOs

---

## Core Value Proposition

### Priority 1: For DAO Treasuries (Primary Target)
```
"With a $5M LP deposit:
 Always LP worst case: -$2.25M (45% drawdown)
 IL Alpha worst case:  -$600K  (12% drawdown)

 Same fee income, but worst-case loss is 1/4.
 Audited smart contracts manage the risk.
 A proposal that can actually pass governance."

The reality for DAO treasuries:
  Aave:              4% yield    → Safe but slow
  Lido:              6-8% yield  → ETH only, ETH price risk
  Raw LP:            15%+ possible → But 49.5% of LPs lose money
  IL Alpha Vault:    15%+ possible → Sharpe 3.66, Max DD -12%

A proposal governance can approve:
  ✅ Sharpe Ratio 3.66 (7x the S&P 500's ~0.5)
  ✅ Max Drawdown -12% (1/4 of Raw LP's -45%)
  ✅ Performance-fee-only (zero fees when there's a loss)
  ✅ ERC-4626 standard (no lockup, withdraw anytime)
  ✅ On-chain transparency (every decision logged as an event)
```

### Priority 2: For Protocol Treasuries (B2B)
```
"Your team's treasury funds are already in LP,
 and IL is eating them away every month.

 Raw LP:      Treasury depleted in 6 months → liquidity goes to 0
 IL Alpha:    Treasury preserved → liquidity maintained for 12+ months

 We don't 'supply' your liquidity.
 We make the LP you're already running last longer."
```

⚠️ **IMPORTANT:** Never pitch as "we supply your liquidity." We pull out during high vol — that's a broken promise. Always frame as "we protect your treasury so liquidity lasts longer."

### Priority 3: For Retail LPs (Phase 2)
```
"While your ETH sits idle, let the vault put it to work.
 It automatically steps out when conditions are risky.
 You only pay fees when you make money."

"49.5% of Uniswap LPs are losing money.
 They earned $199M in fees but lost $260M to IL. Net loss: $61M.
 We automatically pull LP when conditions are dangerous.
 Same fees, fewer losses."
```

---

## B2B Pitch Summary (for governance proposals & outreach)

### Problem
Out of $24.5B in total DAO treasury assets, 67% sits idle. Treasuries want LP-level yields (15%+), but with 49.5% of LPs losing money, governance won't approve it. The result: billions in capital earning 0% yield.

### Why Existing Alternatives Fail
| Alternative | Yield | Problem |
|-------------|-------|---------|
| Hold stablecoins | 0% | Capital inefficiency |
| Aave/Compound | 4-5% | Too low for treasury growth |
| Lido/stETH | 6-8% | ETH-only, ETH price risk |
| Raw LP (Uniswap) | 15-30% | 49.5% of LPs lose money, -45% Max DD |
| Market makers | Variable | $10-50K/mo, unaffordable |
| **IL Alpha Vault** | **15%+** | **Sharpe 3.66, Max DD -12%, perf-fee-only** |

### The Ask
- $1-2M treasury allocation (10-20% of total treasury)
- Governance proposal drafting support (template + testnet performance data)
- Performance report provided after 4-week monitoring period

---

## Key Stats (use in content)

| Stat | Source | Use for |
|------|--------|---------|
| Sharpe Ratio 3.66 | 2yr backtest | **Primary: Risk-adjusted performance** |
| Max DD: -12% vs AlwaysLP -45% | Same backtest | **Primary: Capital preservation** |
| Total DAO treasury assets: $24.5B | DeepDAO 2025 | **Primary: Market size** |
| 67% of DAO treasuries idle | DeepDAO | **Primary: Opportunity** |
| ~1,300 DAOs with $10M+ treasuries | DeepDAO + academic study | **Primary: B2B target count** |
| 49.5% of LPs lose money | Bancor/Topaze Blue study | Supporting: Why DAOs avoid LP |
| Fees $199M, IL $260M, net loss $61M | Same study | Supporting: Quantifying LP risk |
| V3 concentrated LP → 4x IL amplification | 2024 academic paper | Supporting: Why V3/V4 LP is harder |
| IL > fees in 80% of pools | Bancor study | Supporting: Most pools are unprofitable |
| Bunni (V4 hook LP leader) hacked and dead | Sep 2025, $8.4M | Supporting: Why simplicity matters |
| Our backtest: +231% | 2yr real ETH data | Supporting: Absolute return |

---

## Handling Objections

### "AlwaysLP has higher returns though?"
```
In the backtest, AlwaysLP returned +297% vs our +231%.
That's true. This 2-year period was a sideways market, which favors LP.

But:
- Nobody knows if the next 2 years will also be sideways
- In a pump-then-dump (round trip), AlwaysLP accumulates IL in both directions
- Max Drawdown: AlwaysLP loses half its principal in a downturn

We're not selling return maximization — we're selling "defense against the worst case."
Same logic as insurance.
```

### "Aave 4%, Lido 6-8% is good enough?"
```
Different category entirely.
Aave = deposits, Lido = staking, us = LP management.

If 4-8% is enough → use Aave/Lido. Seriously.
If you want 15%+ LP returns but IL scares you → use us.

You wouldn't compare a savings account to stock investing.
Don't directly compare staking to an LP vault either.
```

### "If you pull LP during volatility, liquidity disappears?"
```
Correct. There are short-term moments when liquidity decreases.

But zoom out:
  Raw LP (Always ON):  6 months of IL → treasury depleted → liquidity = 0
  IL Alpha:            IL defense → treasury preserved → 12mo+ of liquidity

  Liquidity at 0 after 6 months  vs  liquidity maintained for 12+ months.
  Which is better for the protocol?
```

### "Is it worth paying the fee?"
```
You're not paying a fee —
you're splitting a portion of profits you couldn't earn on your own.

  Solo LP:     Don't know how → don't do it → earnings $0
  IL Alpha:    Handled for you → earnings $1,350 (after $150 fee)

  $0 vs $1,350. The $150 fee isn't the cost —
  not using us means missing out on $1,350.

  And: zero fees if there's a loss. (Performance fee only)
```

### "You're an unknown project — why should I trust you?"
```
1. Code is open source (verifiable)
2. Audit report to be published (Phase 4)
3. On-chain data is transparent (every decision logged as an event)
4. ERC-4626 standard (no lockup, withdraw anytime)
5. Running testnet control groups (results are public)

Trust is built over time.
We let the data speak for itself.
```

### B2B-specific: "Will this pass governance?"
```
What governance votes need:
  ✅ Risk metrics stated — Sharpe 3.66, Max DD -12%
  ✅ Benchmark comparison — 15%+ vs Aave 4%, Lido 6-8%
  ✅ Exit path — ERC-4626, no lockup, withdraw anytime
  ✅ Cost transparency — Performance-fee-only, zero fees on losses
  ✅ Audit plan — Phase 4, $50-150K budget secured
  ✅ Testnet results — 3-vault control group results published

We provide a draft governance proposal.
Includes testnet data + risk analysis.
```

### B2B-specific: "How does a DAO withdraw?"
```
ERC-4626 standard vault.
  - Instant withdrawal via redeem() call
  - No lockup, no waiting period
  - If LP is active, vault auto-recalls before withdrawal
  - Can be called directly from a multisig wallet
  - emergencyWithdraw() available for emergencies (owner only)
```

---

## Differentiator (one chart for all content)

```
                    What happens during high volatility?

Arrakis:     Raises fees (keeps LP on)              → Still exposed to IL
Gamma:       Widens range (keeps LP on)              → Still exposed to IL
Charm:       Rebalances range (keeps LP on)          → Still exposed to IL
Maverick:    LP decides on their own                 → Manual, expert-only
Yield Basis: Offsets IL with leverage                 → Adds leverage risk

IL Alpha:    Turns LP off entirely                   → IL exposure = 0
```

---

## Tone & Style Guide

```
DO:
  ✅ Speak with data (charts, numbers, on-chain evidence)
  ✅ Be honest about caveats ("backtest limitations", "not yet battle-tested")
  ✅ Show technical depth (math, architecture)
  ✅ Share design decisions ("why we built it this way")
  ✅ Be humble but confident

DON'T:
  ❌ "Launching soon!", "To the moon!", price mentions
  ❌ Promise specific dates
  ❌ Trash other projects (comparison is OK, bashing is NOT)
  ❌ Over-promise ("guaranteed returns" etc.)
  ❌ Dumb down the tech (our strength is technical depth)
```

---

## Content Calendar Template

```
One tweet per day, short building log style:

  Format:
  [Day N] IL Alpha Vault
  Today's progress: {1 line}
  {screenshot or 1 data point}
  #BuildInPublic #DeFi #UniswapV4

  Weekly routine:
  Mon: Technical content (math, architecture, design decisions)
  Tue: Building log (what got done today)
  Wed: Industry insights (LP stats, competitor analysis)
  Thu: DAO treasury analysis (idle asset breakdown for specific DAOs, governance forum posts)
  Fri: Testnet weekly report (performance data, control group comparison)
  Sat/Sun: Flexible (Q&A, lighter content, or take a break)

  B2B monthly routine:
  Week 1: Publish DAO treasury performance comparison report
  Week 2: Post proposals to target DAO governance forums (1-2)
  Week 3: Performance update for existing partners
  Week 4: Research + outreach to new DAOs
```

---

## Related Documents
- [ROADMAP.md](./ROADMAP.md) — Full commercialization roadmap
- [COMPETITIVE.md](./COMPETITIVE.md) — Competitor analysis
- [../TODOS.md](../TODOS.md) — Implementation tasks
- [roadmap.html](./roadmap.html) — Visual roadmap (browser)
