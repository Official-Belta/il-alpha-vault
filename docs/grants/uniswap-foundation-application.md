# Uniswap Foundation — IL Alpha Grant Applications

## Application Strategy

UF는 단일 그랜트가 아니라 여러 프로그램을 운영 중. IL Alpha에 해당하는 3개를 동시 신청.

| # | 프로그램 | 목적 | 신청 링크 |
|---|---------|------|----------|
| **A** | **v4 Hook Design Lab (Cohort 2)** | 멘토링 + 펀딩 + GTM + 감사보조 | [신청](https://share.hsforms.com/1y57UxXGGSrKc7d8v5opZzwsdca9) |
| **B** | **UFSF Audit Subsidies** | 감사비 최대 100% 커버 | [신청](https://areta.fillout.com/UFSF) |
| **C** | **v4 Hooks Support** | V4 hook 기술 지원 | [신청](https://share.hsforms.com/1O91L2eugREerAJJQt1jFTQs8pgg) |

A가 메인, B가 감사비 절약, C가 추가 지원. A가 안 되면 **General Grants**([신청](https://share.hsforms.com/1fxQjPQTgTYmPwlYxxKlSGQsdca9))로 폴백.

---

# Application A: v4 Hook Design Lab — Cohort 2

## Project Name
IL Alpha

## One-Line Description
A Uniswap V4 hook that protects DAO treasury capital from impermanent loss by automatically removing LP positions when volatility exceeds fee income.

## Hook Category
**Dynamic Risk Management** — Binary LP on/off toggle based on real-time volatility vs fee yield comparison. Related to but distinct from Cohort 1's "Dynamic Fees" category.

Cohort 1 focused on:
- JIT Liquidity (EulerSwap)
- Dynamic Fees (Aegis, Dynamo DEX)
- Rehypothecation (Bunni)

IL Alpha introduces a new hook category: **IL-Aware LP Toggle** — the first hook that removes LP entirely when expected value is negative.

## Problem Statement

**$16.4B in DAO treasury capital sits idle at 0% yield because LP means impermanent loss.**

- 49.5% of Uniswap V3 LPs lose more to IL than they earn in fees (Bancor/Topaze Blue study)
- Net loss across V3 LPs: -$61M (fees $199M − IL $260M)
- V3/V4 concentrated liquidity amplifies IL by 4× vs V2
- 1,300+ DAOs with $10M+ treasuries avoid LP entirely due to governance risk aversion
- Result: massive capital that *could* be providing Uniswap liquidity stays on the sidelines

The #1 barrier to institutional capital entering Uniswap concentrated liquidity is impermanent loss. Solving IL unlocks the next wave of Uniswap TVL.

## Solution

IL Alpha is a V4 hook + ERC-4626 vault that makes a binary decision every hour:

```
If fee_yield > IL_cost → LP stays active (earning fees)
If fee_yield < IL_cost → LP is removed entirely (capital preserved)
```

**How it works:**
1. `afterSwap` hook updates an on-chain EWMA volatility oracle on every swap
2. Keeper bot blends off-chain volatility data (Binance) with on-chain estimate
3. Computes fee yield (pool fee rate × EWMA volume) vs IL cost (0.5 × σ² × concentration)
4. Binary toggle: deploy all liquidity or remove all liquidity
5. 24-hour cooldown prevents churn. Volume spike trigger for emergency removal.

**Key innovation:** Every existing LP manager (Arrakis, Gamma, Charm) keeps LP active during high volatility. IL Alpha is the first protocol that **removes LP entirely** when the expected value is negative.

## Technical Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Uniswap V4 │◄────│ ILAlphaHook  │────►│    Keeper     │
│  PoolManager│     │ (afterSwap)  │     │  (1hr cycle)  │
│  Singleton  │     │ EWMA Oracle  │     │ Binance + Web3│
└──────┬──────┘     └──────┬───────┘     └───────────────┘
       │                   │
       │            ┌──────▼───────┐
       └────────────│ ILAlphaVault │
                    │  (ERC-4626)  │
                    │ deposit/     │
                    │ withdraw/    │
                    │ rebalance    │
                    └──────────────┘
```

**Contracts:**
- `ILAlphaHook.sol` (223 lines) — V4 hook with EWMA vol oracle, LP toggle signal
- `ILAlphaVault.sol` (325 lines) — ERC-4626 vault with real-time LP valuation, TWAP manipulation check, withdrawal fee
- `BaseVault.sol` (54 lines) — Shared ERC-4626 base with virtual shares (inflation attack prevention)
- 2 control vaults: `AlwaysLPVault`, `HODLVault` — for rigorous A/B comparison

**Security measures:**
- Real-time LP valuation via pool tick (not stale accounting — lesson from Gamma $6.4M hack)
- TWAP check on deposit/withdraw (prevents price manipulation)
- Virtual shares (prevents ERC-4626 inflation attacks)
- 0.1% withdrawal fee (protects existing depositors)
- Reentrancy guards on all state-changing functions
- Volume spike trigger bypasses cooldown for emergency LP removal

## Current Status

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1: Python Backtest | **Complete** | 99 tests passing. 2-year real ETH/USDC data. |
| Phase 2: Solidity Contracts | **Complete** | 65 tests passing (incl. fuzz). Full test coverage. |
| Phase 3: Testnet Validation | **Active** | Deployed on Ethereum Sepolia. Keeper bot live (1hr cycles). |
| Phase 4: Mainnet | Planned | Pending audit + Design Lab support |

**Testnet deployment (Ethereum Sepolia):**
- ILAlphaHook: `0xB3150D39893dC6842Bd4c0EB6D0Fdab4A6211040`
- ILAlphaVault: `0x8A4A048e5da48De8dCa28686a2d326048796E4B1`
- AlwaysLPVault: `0x7F6699ECB6cF92e385Fa919Fe2810f79b5C52040`
- HODLVault: `0x979C2460b29C0e8992FEd8a3BA0a4284B2a10C0C`

**Live links:**
- Milestone site: https://official-belta.github.io/il-alpha-site/
- Testnet dashboard: https://official-belta.github.io/il-alpha-site/dashboard/dashboard.html
- Investment thesis: https://official-belta.github.io/il-alpha-site/thesis.html
- GitHub: [REPO_URL]

## Backtest Results (2-Year Real ETH/USDC Data)

| Metric | IL Alpha | AlwaysLP | HODL |
|--------|----------|----------|------|
| **Sharpe Ratio** | **3.66** | 3.24 | 1.11 |
| **Max Drawdown** | **-12%** | -45% | -65% |
| Cumulative Return | +231% | +297% | +91% |
| Capital Preserved (worst) | 88% | 55% | 35% |

IL Alpha sacrifices ~22% raw return for **73% reduction in worst-case drawdown**. This is the exact tradeoff that DAO treasury governance demands.

## Why This Matters for Uniswap

1. **Unlocks institutional capital for Uniswap V4.** $24.5B in DAO treasuries avoid LP because of IL. IL Alpha makes LP governance-approvable → more Uniswap TVL.

2. **New hook category for V4.** Cohort 1 covered JIT, Dynamic Fees, Rehypothecation. IL-aware LP toggling is an unexplored hook category with massive market impact.

3. **Fills the Bunni vacuum.** Bunni V2 was the leading V4 hook LP protocol before its $8.4M hack (Sep 2025). That slot is vacant. A simpler, well-audited alternative benefits the entire V4 ecosystem.

4. **Open-source public good.** The EWMA volatility oracle and binary LP toggle mechanism are reusable by other V4 hook developers. All code published under MIT license.

## What We Need from the Design Lab

| Support Area | What We Need |
|-------------|-------------|
| **Audit subsidy** | Security audit is our #1 blocker. UFSF access would be transformative. |
| **Protocol engineering** | Review of hook-vault interaction patterns, gas optimization |
| **GTM support** | DAO treasury outreach strategy, governance proposal templates |
| **Router rebates** | Reduce gas cost for keeper rebalance operations |
| **Ecosystem connections** | Introductions to DAO treasury managers, V4 ecosystem partners |

## Milestones

| # | Milestone | Deliverable | Timeline |
|---|-----------|-------------|----------|
| M1 | Testnet validation report | Performance comparison: IL Alpha vs AlwaysLP vs HODL across 2+ vol regimes | Month 1 |
| M2 | Security audit complete | Published audit report, all critical/high findings resolved | Month 2-3 |
| M3 | Mainnet deployment | Live on Base or Arbitrum (where V4 is most active) | Month 3-4 |
| M4 | First DAO partnership | $1M+ TVL from governance-approved DAO treasury allocation | Month 4-6 |
| M5 | Multi-pool expansion | wstETH/ETH + USDC/USDT pools live | Month 6-8 |

## Team

**[Founder Name]**
- Solo founder/developer
- Background: [BRIEF BIO]
- Built IL Alpha end-to-end: Python backtest (99 tests) → Solidity contracts (65 tests) → Testnet deployment → Keeper bot → Public site
- Prior experience: [RELEVANT EXPERIENCE]

## Competitive Landscape

| Protocol | IL Strategy | V4 Native | LP Toggle |
|----------|------------|-----------|-----------|
| Arrakis | Raise fees during vol | Yes (hook) | No (always on) |
| Gamma | Widen range | No (V3) | No (always on) |
| Charm | Rebalance range | No (V3) | No (always on) |
| Bunni | Dynamic curves | Yes (dead) | No (always on) |
| **IL Alpha** | **Remove LP entirely** | **Yes** | **Yes** |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Smart contract exploit | Audit + simple design (one hook, one vault, one decision) + TWAP checks |
| Keeper failure | Public `rebalance()` fallback + Chainlink Automation planned |
| Strategy underperformance in bull | Transparent disclosure. We optimize Sharpe/DD, not max return. |
| Low TVL at launch | Deposit caps (Charm model) + DAO partnerships pre-secured |

## Open Source Commitment

All code, research, and backtest data will remain open source under MIT license. The EWMA volatility oracle is designed to be reusable by other V4 hook developers.

---

# Application B: UFSF Audit Subsidies

**신청 링크:** https://areta.fillout.com/UFSF

**프로젝트:** IL Alpha — V4 Hook 기반 IL 보호 볼트
**코드 규모:** ILAlphaHook (223줄) + ILAlphaVault (325줄) + BaseVault (54줄) = ~600줄 핵심 코드
**테스트 커버리지:** 65 Solidity tests (fuzz 포함), 99 Python tests
**감사 필요 이유:** 메인넷 배포 전 필수. Bunni V2가 감사 없이 런칭 → $8.4M 해킹 사망.
**희망 감사 기관:** Spearbit, Code4rena, Trail of Bits (UFSF 네트워크 내)
**예상 비용:** $50K-$150K (코드 규모 대비)

---

# Application C: v4 Hooks Support

**신청 링크:** https://share.hsforms.com/1O91L2eugREerAJJQt1jFTQs8pgg

**프로젝트:** IL Alpha
**Hook 유형:** afterSwap — EWMA volatility oracle + LP toggle signal
**현재 상태:** Sepolia 배포 완료, keeper 가동 중
**필요한 지원:** 기술 리뷰, 가스 최적화, V4 PoolManager 통합 패턴 검증

---

# Fallback: General Grants

**신청 링크:** https://share.hsforms.com/1fxQjPQTgTYmPwlYxxKlSGQsdca9

Hook Design Lab 미선정 시 사용.

**요청 금액: $150,000**

| Item | Amount | Purpose |
|------|--------|---------|
| Security audit | $80,000 | Professional audit (Code4rena competitive) |
| Mainnet deployment | $10,000 | Gas costs, infrastructure setup |
| Keeper infrastructure | $12,000 | 12 months server + RPC costs |
| Development | $48,000 | 6 months part-time (multi-pool, improvements) |

**지급 구조:** 30% 승인 시, 40% 감사 완료 시, 30% 메인넷 배포 시.
