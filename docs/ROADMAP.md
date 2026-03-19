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
| Base mainnet deploy | 5 contracts via forge script | ⏳ ENG 진행 중 |
| Keeper Base 전환 | Base RPC, real ETH/USDC pool | ⏳ |
| Dashboard Base 전환 | Real mainnet data | ⏳ |

### 4.2 Seed Operation ($1.2K, 4 weeks)

```
Wallet Setup:
  Deployer  (시드 A) — contract deployment
  Operator  (시드 A) — $400×3 vault seed (1,200 USDC)
  Treasury  (시드 B) — Gnosis Safe, vault owner
  Sentinel  (시드 C) — keeper bot PK

Vaults:
  ILAlphaVault:  $400 USDC → ETH/USDC V4 pool (with hook)
  AlwaysLPVault: $400 USDC → same pool (no hook, control)
  HODLVault:     $400 USDC → hold only (control)

Deposit cap: 비활성화 (본인 자금만, 외부 비공개)
Unaudited 고지: 사이트 + 컨트랙트에 명시
```

### 4.3 Revenue Model — Phased Fee Structure

```
Stage 1: Launch (TVL < $5M)
├─ Performance Fee: 10%
├─ Management Fee: 0%
├─ Withdrawal Fee: 0%        ← 감사 후 재추가 검토
└─ "수익 안 나면 우리도 안 번다"

Stage 2: Growth (TVL $5-20M)
├─ Performance Fee: 15%
├─ Management Fee: 0.5%/yr
└─ Withdrawal Fee: 0.1% (감사 후)

Stage 3: Established (TVL $20M+)
├─ Performance Fee: 15-20%
├─ Management Fee: 1%/yr
└─ Withdrawal Fee: 0.1%
```

---

## Phase 5: Grants & Audit (Month 1-3)

### 5A. UFSF Audit Subsidy — 최우선

| Item | Detail |
|------|--------|
| 프로그램 | Uniswap Foundation Security Fund (Areta 운영) |
| 보조율 | 감사비 최대 100% |
| 신청 시점 | 코드 프리즈 + mainnet 4주 운영 데이터 확보 후 |
| 신청 링크 | https://areta.fillout.com/UFSF |
| 코드 규모 | Hook 446줄 + Vault 448줄 = ~900줄 핵심 |

### 5B. 추가 그랜트 (병렬)

| 프로그램 | 목표 금액 | 확률 | 시점 |
|---------|----------|------|------|
| Hook Design Lab (Cohort 2) | 펀딩+멘토링+GTM | 중 | mainnet 데이터 후 |
| v4 Hooks Support | 기술 지원 | 중-높 | 즉시 |
| Arbitrum Questbook | $25-75K | 중 | 병렬 |
| Base Ecosystem | $50-150K | 중 | 병렬 |

### 5C. 전문 감사 (UFSF 승인 후)

감사 기관 (UFSF 네트워크):
- Spearbit, Trail of Bits, Code4rena, OpenZeppelin
- 코드 프리즈 상태에서 감사 → 수정 → 재검증 → 캡 오픈

---

## Phase 6: DAO Go-to-Market (Month 2-6)

### 6A. B2B — DAO Treasury Acquisition (Primary GTM)

**전제:** mainnet 4주+ 실데이터 + 감사 완료 (또는 진행 중)

**Target:** 3-5 DAO partners at $1-2M each = $3-10M TVL

| Step | What | Timeline |
|------|------|----------|
| 1 | 20 target DAOs identified | ✅ Done |
| 2 | Governance proposal template (EN/KO) | ✅ Done |
| 3 | Post on top 3 DAO forums (Gnosis, ENS, Polygon) | Month 2-3 |
| 4 | Close first DAO partnership | Month 3-4 |
| 5 | Case study → pitch next 4 | Month 4-6 |

**Top 3 아웃리치 타겟:**
1. **Gnosis DAO** — 새 트레저리 매니저(Noca)가 Q1 2026 "유휴 자본 배치" 미션
2. **ENS DAO** — 포럼 활발, karpatkey가 16K+ ETH 관리
3. **Polygon** — $1.3B 유휴 스테이블코인, 연 $70M 기회비용

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
| Rehypothecation | LP OFF 시 유휴 자금 → Aave/Compound (Bunni가 못 한 걸 단순하게) |
| Share composability | vault share → Morpho/Euler 담보로 사용 가능하게 통합 |
| Audit + track record | 무중단 운영 = 신뢰 축적 |
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
| DAO treasuries | $24.5B idle, scared of IL | "Sharpe 3.66, DD -12%. Governance-ready." | **1순위** |
| Protocol treasuries | Treasury melting from IL | "12mo instead of 6mo." | **2순위** |
| Existing LPs | 49.5% unprofitable | "Stop losing." | 3순위 |
| LP-curious holders | Want >4% but scared | "Higher yield, auto risk mgmt." | 4순위 |

---

## Financial Projections

### Year 1 (B2B DAO 파트너십 기준)
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
Key       Deploy      UFSF申請    1st DAO       5 DAOs       Established
```

---

## Immediate Next Actions

1. ✅ ~~B2B 피봇 (메시징/문서)~~
2. ✅ ~~4-round Trail of Bits audit (internal)~~
3. ✅ ~~Governance proposal template (EN/KO)~~
4. ✅ ~~DAO target list (20 DAOs, 3 tiers)~~
5. ✅ ~~Grant strategy (UF 3 programs + Arbitrum/Base)~~
6. ⏳ **Base mainnet 배포** ($1.2K seed) — ENG 진행 중
7. ⏳ **4주 실운영** — 성과 데이터 축적
8. ⏳ **UFSF 감사 보조금 신청** — 4주 데이터 후
9. ⏳ **Litepaper** — mainnet 데이터 포함
10. ⏳ **DAO 아웃리치** — 감사 진행 중 + 실데이터 확보 후

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
