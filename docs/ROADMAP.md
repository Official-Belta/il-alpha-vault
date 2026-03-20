# IL Alpha — Commercialization Roadmap

Updated: 2026-03-20 (reflects B2B pivot, mainnet direct, audit results)

---

## Current Status

```
Phase 1 (Python Backtest)       ████████████ 100%  — 99 tests, thesis validated
Phase 2 (Solidity Contracts)    ████████████ 100%  — 65 tests (fuzz incl.), 4-round audit clean
Phase 3 (Testnet Validation)    ████████████ 100%  — Sepolia deployed, keeper live, dashboard live
Phase 4 (Base Mainnet)          ██░░░░░░░░░░  15%  — Code freeze done, F-2 guard added, deploying
```

---

## Phase 3: Testnet Validation — COMPLETE ✅

- CREATE2 hook deployment on Ethereum Sepolia
- Keeper bot live (1hr cycles, Binance vol → on-chain)
- 3 vaults deployed: ILAlpha vs AlwaysLP vs HODL
- Performance dashboard (Chart.js, real-time)
- 4-round Trail of Bits security audit: 0 Critical, 0 High, 89/100 readiness

---

## Phase 4: Base Mainnet (NOW — April 2026)

### 4.1 Code Freeze & Deploy

| Step | What | Status |
|------|------|--------|
| Code freeze | All features complete, no more changes | ✅ Done |
| F-2 setLPRange guard | Prevent range change while LP deployed | ✅ Done |
| Withdrawal fee removed | ERC-4626 compliance, simplicity | ✅ Done |
| Volume spike trigger | Emergency LP removal bypasses cooldown | ✅ Done |
| TWAP check | Deposit/withdraw manipulation protection | ✅ Done |
| Base mainnet deploy | 5 contracts via forge script | ⏳ ENG in progress |
| Keeper Base migration | Base RPC, real ETH/USDC pool | ⏳ |
| Dashboard Base migration | Real mainnet data | ⏳ |

### 4.2 Seed Operation ($1.2K, 4 weeks)

```
Wallet Setup:
  Deployer  (Seed A) — contract deployment
  Operator  (Seed A) — $400×3 vault seed (1,200 USDC)
  Treasury  (Seed B) — Gnosis Safe, vault owner
  Sentinel  (Seed C) — keeper bot PK

Vaults:
  ILAlphaVault:  $400 USDC → ETH/USDC V4 pool (with hook)
  AlwaysLPVault: $400 USDC → same pool (no hook, control)
  HODLVault:     $400 USDC → hold only (control)

Deposit cap: Disabled (own funds only, not open to external deposits)
Unaudited notice: Displayed on site + contracts
```

### 4.3 Revenue Model — Phased Fee Structure

```
Stage 1: Launch (TVL < $5M)
├─ Performance Fee: 10%
├─ Management Fee: 0%
├─ Withdrawal Fee: 0%        ← May revisit after audit
└─ "If we don't generate profit, we don't earn either"

Stage 2: Growth (TVL $5-20M)
├─ Performance Fee: 15%
├─ Management Fee: 0.5%/yr
└─ Withdrawal Fee: 0.1% (post-audit)

Stage 3: Established (TVL $20M+)
├─ Performance Fee: 15-20%
├─ Management Fee: 1%/yr
└─ Withdrawal Fee: 0.1%
```

---

## Phase 5: Grants & Audit (Month 1-3)

### 5A. UFSF Audit Subsidy — Top Priority

| Item | Detail |
|------|--------|
| Program | Uniswap Foundation Security Fund (operated by Areta) |
| Subsidy rate | Up to 100% of audit costs |
| Application timing | After code freeze + 4 weeks of mainnet operational data |
| Application link | https://areta.fillout.com/UFSF |
| Code scope | Hook 446 lines + Vault 448 lines = ~900 lines core |

### 5B. Additional Grants (Parallel)

| Program | Target Amount | Probability | Timing |
|---------|----------|------|------|
| Hook Design Lab (Cohort 2) | Funding + mentorship + GTM | Medium | After mainnet data |
| v4 Hooks Support | Technical support | Medium-High | Immediately |
| Arbitrum Questbook | $25-75K | Medium | Parallel |
| Base Ecosystem | $50-150K | Medium | Parallel |

### 5C. Professional Audit (After UFSF Approval)

Audit firms (UFSF network):
- Spearbit, Trail of Bits, Code4rena, OpenZeppelin
- Audit on frozen code → fix → re-verify → open deposit cap

---

## Phase 6: DAO Go-to-Market (Month 2-6)

### 6A. B2B — DAO Treasury Acquisition (Primary GTM)

**Prerequisite:** 4+ weeks of mainnet live data + audit complete (or in progress)

**Target:** 3-5 DAO partners at $1-2M each = $3-10M TVL

| Step | What | Timeline |
|------|------|----------|
| 1 | 20 target DAOs identified | ✅ Done |
| 2 | Governance proposal template (EN/KO) | ✅ Done |
| 3 | Post on top 3 DAO forums (Gnosis, ENS, Polygon) | Month 2-3 |
| 4 | Close first DAO partnership | Month 3-4 |
| 5 | Case study → pitch next 4 | Month 4-6 |

**Top 3 Outreach Targets:**
1. **Gnosis DAO** — New treasury manager (Noca) has a Q1 2026 "deploy idle capital" mission
2. **ENS DAO** — Active forum, karpatkey manages 16K+ ETH
3. **Polygon** — $1.3B idle stablecoins, $70M/yr opportunity cost

**Pitch:** "LP yield with Sharpe 3.66, Max DD -12%. Performance-fee-only. ERC-4626. No lockup."

### 6B. B2C — Retail LP (Secondary, Organic)

| Channel | Strategy |
|---------|----------|
| Performance marketing | Real on-chain data: "Last 30d: ILAlpha +X%, AlwaysLP +Y%, HODL +Z%" |
| DeFi community | CT, Farcaster. Research-grade threads |
| Educational content | "IL is gamma exposure" blog/video |
| Dune dashboard | Public on-chain tracking |

### 6C. Multi-pool Expansion

1. **ETH/USDC** — launch pair (high vol = maximum strategy value)
2. **wstETH/ETH** — safest pair, DAO treasury friendly
3. **USDC/USDT** — stablepair, IL ≈ 0
4. **BTC/ETH** — market expansion
5. **Long-tail** — B2B white-label

---

## Phase 7: Moat Building (Month 6-12)

| Moat | How |
|------|-----|
| Data advantage | More runtime = more accurate vol oracle |
| Rehypothecation | Route idle funds to Aave/Compound when LP is off (what Bunni couldn't do, simplified) |
| Share composability | Integrate vault shares as collateral on Morpho/Euler |
| Audit + track record | Uninterrupted operation = trust accumulation |
| V4 hook ecosystem | First-mover as V4 grows |

---

## Phase 8: Token / Governance (conditional)

Decision point: only after PMF confirmed and TVL > $5M.

**Token YES:**
- Pro: community participation, flywheel, liquidity bootstrap
- Con: regulatory risk, token price management, dilution

**Token NO:**
- Pro: pure revenue model, simpler regulatory, operational focus
- Con: harder flywheel, weaker community incentives

---

## Product Positioning

### What we are NOT
- NOT a staking alternative (Lido/EtherFi 4-8%)
- NOT a lending alternative (Aave 4-5%)
- NOT a liquidity guarantee (we pull out during high vol)
- NOT Protocol Owned Liquidity management (that's Arrakis)

### What we ARE
- **Treasury-grade LP management** for capital that needs 15%+ with capital preservation
- For DAO treasuries that can't afford 45% drawdowns
- Automatic, ERC-4626, no lockup

### Customer segments
| Segment | Pain | Pitch | Priority |
|---------|------|-------|----------|
| DAO treasuries | $24.5B idle, scared of IL | "Sharpe 3.66, DD -12%. Governance-ready." | **#1** |
| Protocol treasuries | Treasury melting from IL | "12mo instead of 6mo." | **#2** |
| Existing LPs | 49.5% unprofitable | "Stop losing." | #3 |
| LP-curious holders | Want >4% but scared | "Higher yield, auto risk mgmt." | #4 |

---

## Financial Projections

### Year 1 (Based on B2B DAO Partnerships)
```
3 DAO partners × $2M avg = $6M TVL
  Performance fee: ~$6.4K/mo ($77K/yr)

5 DAO partners × $2M avg = $10M TVL
  Performance fee: ~$10.6K/mo ($128K/yr)

Breakeven: ~$5M TVL
```

### Year 3 (Steady State)
```
              TVL      Monthly Rev   Monthly Cost   Monthly Profit
──────────────────────────────────────────────────────────────────
Pessimistic   $10M     $24K          $11K           $13K
Conservative  $15M     $36K          $11K           $25K
Optimistic    $25M     $60K          $11K           $49K
```

---

## Timeline Summary

```
         NOW          1mo          3mo          6mo          12mo
          |            |            |             |            |
Phase 4   ████                                                  Base Mainnet
Phase 5        ████████████                                     Grants + Audit
Phase 6                    ████████████████                     DAO GTM
Phase 7                            ████████████████             Moat
Phase 8                                    ????                 Token?
          |            |            |             |            |
TVL       $1.2K       $1.2K       $6M           $10M         $15-20M
Revenue   $0          $0          ~$6K/mo       ~$17K/mo     ~$36K/mo
Key       Deploy      UFSF App    1st DAO       5 DAOs       Established
```

---

## Immediate Next Actions

1. ✅ ~~B2B pivot (messaging/docs)~~
2. ✅ ~~4-round Trail of Bits audit (internal)~~
3. ✅ ~~Governance proposal template (EN/KO)~~
4. ✅ ~~DAO target list (20 DAOs, 3 tiers)~~
5. ✅ ~~Grant strategy (UF 3 programs + Arbitrum/Base)~~
6. ⏳ **Base mainnet deployment** ($1.2K seed) — ENG in progress
7. ⏳ **4-week live operation** — Accumulate performance data
8. ⏳ **UFSF audit subsidy application** — After 4 weeks of data
9. ⏳ **Litepaper** — Including mainnet data
10. ⏳ **DAO outreach** — After audit in progress + live data secured

---

## Related Documents

- **[COMPETITIVE.md](./COMPETITIVE.md)** — Competitor analysis
- **[MESSAGING.md](./MESSAGING.md)** — B2B messaging & positioning
- **[ENG_HANDOFF.md](./ENG_HANDOFF.md)** — Engineering execution plan
- **[grant-strategy.md](./grant-strategy.md)** — Grant application strategy
- **[governance-proposal-template.md](./governance-proposal-template.md)** — DAO proposal template
- **[dao-target-list.md](./dao-target-list.md)** — 20 target DAOs
- **[grants/uniswap-foundation-application.md](./grants/uniswap-foundation-application.md)** — UF application
- **[competitive-notes-gemini.md](./competitive-notes-gemini.md)** — Long-term competitive reference
- **[audit/v4/02-final-assessment.md](./audit/v4/02-final-assessment.md)** — Latest audit report
