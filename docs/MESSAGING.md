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

### 1순위: For DAO Treasuries (Primary Target)
```
"$5M LP 예치 시:
 Always LP 최악: -$2.25M (45% drawdown)
 IL Alpha 최악:  -$600K  (12% drawdown)

 같은 수수료를 벌면서, 최악의 손실이 1/4.
 감사된 스마트컨트랙트가 리스크를 관리합니다.
 거버넌스 투표에서 통과시킬 수 있는 제안입니다."

DAO 트레저리의 현실:
  Aave에 넣으면:     4% yield    → 안전하지만 느림
  Lido에 넣으면:     6-8% yield  → ETH 전용, ETH 리스크
  직접 LP:           15%+ 가능   → 하지만 49.5%가 손실
  IL Alpha Vault:    15%+ 가능   → Sharpe 3.66, Max DD -12%

거버넌스에서 통과시킬 수 있는 제안:
  ✅ Sharpe Ratio 3.66 (S&P 500 ~0.5 대비 7배)
  ✅ Max Drawdown -12% (Raw LP -45% 대비 1/4)
  ✅ Performance-fee-only (손실 시 수수료 0)
  ✅ ERC-4626 표준 (락업 없음, 언제든 인출)
  ✅ 온체인 투명성 (모든 결정이 이벤트 로그)
```

### 2순위: For Protocol Treasuries (B2B)
```
"당신 팀이 이미 LP에 넣고 있는 트레저리 자금,
 IL로 매달 녹고 있죠.

 직접 LP:     6개월 만에 트레저리 소진 → 유동성 0
 IL Alpha:    트레저리 보전 → 12개월+ 유동성 유지

 우리가 유동성을 '공급'하는 게 아닙니다.
 당신이 이미 넣고 있는 LP를 '더 오래 유지'시켜드립니다."
```

⚠️ **IMPORTANT:** Never pitch as "we supply your liquidity." We pull out during high vol — that's a broken promise. Always frame as "we protect your treasury so liquidity lasts longer."

### 3순위: For Retail LPs (Phase 2)
```
"당신 ETH가 놀고 있는 동안, vault가 대신 일하게 하세요.
 위험하면 자동으로 쉽니다.
 돈 벌었을 때만 수수료를 냅니다."

"Uniswap LP의 49.5%가 돈을 잃고 있습니다.
 수수료 $199M 벌었는데, IL로 $260M 잃음. 순손실 $61M.
 우리는 위험할 때 자동으로 LP를 끕니다.
 같은 수수료, 더 적은 손실."
```

---

## B2B Pitch Summary (for governance proposals & outreach)

### Problem
DAO 트레저리 총 $24.5B 중 67%가 유휴 상태. LP 수익률(15%+)을 원하지만 49.5%의 LP가 손실을 보는 현실 때문에 거버넌스에서 승인이 안 됨. 결과적으로 수조 원의 자본이 0% 수익률로 방치.

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
- $1-2M 트레저리 배분 (전체 트레저리의 10-20%)
- 거버넌스 제안서 작성 지원 (템플릿 + 테스트넷 성과 데이터)
- 4주 모니터링 후 성과 리포트 제공

---

## Key Stats (use in content)

| Stat | Source | Use for |
|------|--------|---------|
| Sharpe Ratio 3.66 | 2yr backtest | **Primary: Risk-adjusted performance** |
| Max DD: -12% vs AlwaysLP -45% | Same backtest | **Primary: Capital preservation** |
| DAO 트레저리 총 $24.5B | DeepDAO 2025 | **Primary: Market size** |
| DAO 트레저리의 67% 유휴 | DeepDAO | **Primary: Opportunity** |
| $10M+ 트레저리 DAO: ~1,300개 | DeepDAO + academic study | **Primary: B2B target count** |
| LP의 49.5%가 손실 | Bancor/Topaze Blue study | Supporting: Why DAOs avoid LP |
| 수수료 $199M, IL $260M, 순손실 $61M | Same study | Supporting: Quantifying LP risk |
| V3 concentrated LP → IL 4배 증폭 | 2024 academic paper | Supporting: Why V3/V4 LP is harder |
| 풀의 80%에서 IL > 수수료 | Bancor study | Supporting: Most pools are unprofitable |
| Bunni (V4 hook LP leader) 해킹 사망 | Sep 2025, $8.4M | Supporting: Why simplicity matters |
| 우리 백테스트: +231% | 2yr real ETH data | Supporting: Absolute return |

---

## Handling Objections

### "AlwaysLP가 수익률 더 높은데?"
```
백테스트에서 AlwaysLP +297% vs 우리 +231%.
맞음. 이 2년이 횡보장이라 LP에 유리했음.

하지만:
- 다음 2년도 횡보장인지 아무도 모름
- 급등 후 급락 (왕복) 시 Always LP는 양방향 IL 누적
- Max Drawdown: AlwaysLP는 하락장에서 원금 반토막

우리가 파는 건 수익 극대화가 아니라 "최악의 경우 방어."
보험과 같은 논리.
```

### "Aave 4%, Lido 6-8%면 충분한데?"
```
카테고리가 다름.
Aave = 예금, Lido = 스테이킹, 우리 = LP 관리.

4-8%로 충분하면 → Aave/Lido 쓰세요. 진심.
15%+ LP 수익을 원하는데 IL이 무서우면 → 우리를 쓰세요.

예금이랑 주식투자를 비교하지 않듯이,
스테이킹이랑 LP vault를 직접 비교하면 안 됨.
```

### "위험할 때 LP 빼면 유동성이 사라지잖아?"
```
맞음. 단기적으로 유동성이 줄어드는 순간 있음.

하지만 장기로 보면:
  직접 LP (Always ON):  6개월 IL → 트레저리 소진 → 유동성 0
  IL Alpha:             IL 방어 → 트레저리 보전 → 12mo+ 유동성 유지

  6개월 뒤 유동성 0  vs  12개월+ 유동성 유지
  뭐가 프로토콜한테 나은가?
```

### "수수료 내고 쓸 가치가 있나?"
```
수수료를 내는 게 아니라,
혼자서는 못 버는 돈의 일부를 나누는 것.

  혼자 LP:    몰라서 안 함 → 수익 $0
  IL Alpha:   알아서 해줌 → 수익 $1,350 (수수료 $150 차감 후)

  $0 vs $1,350. 수수료 $150이 아까운 게 아니라,
  안 쓰면 $1,350을 못 버는 것.

  그리고: 손실 나면 수수료 0원. (Performance fee only)
```

### "무명 프로젝트인데 왜 믿어?"
```
1. 코드가 오픈소스 (검증 가능)
2. 감사 리포트 공개 예정 (Phase 4)
3. 온체인 데이터 투명 (모든 결정이 이벤트 로그)
4. ERC-4626 표준 (락업 없음, 언제든 인출)
5. 테스트넷 대조군 운영 중 (결과 공개)

신뢰는 시간이 만드는 것.
우리는 데이터로 보여줌.
```

### B2B 전용: "거버넌스에서 통과될까?"
```
거버넌스 투표에 필요한 요소:
  ✅ 리스크 지표 명시 — Sharpe 3.66, Max DD -12%
  ✅ 벤치마크 비교 — Aave 4%, Lido 6-8% 대비 15%+
  ✅ 탈출 경로 — ERC-4626, 락업 없음, 언제든 인출
  ✅ 비용 투명성 — Performance-fee-only, 손실 시 수수료 0
  ✅ 감사 계획 — Phase 4, $50-150K 예산 확보
  ✅ 테스트넷 성과 — 3-vault 대조군 결과 공개

우리가 거버넌스 제안서 초안을 제공합니다.
테스트넷 데이터 + 리스크 분석 포함.
```

### B2B 전용: "DAO가 어떻게 인출하나?"
```
ERC-4626 표준 vault.
  - redeem() 호출로 즉시 인출
  - 락업 없음, 대기 기간 없음
  - LP 활성 중이면 vault가 자동 회수 후 인출
  - 멀티시그 지갑에서 직접 호출 가능
  - 긴급 시 emergencyWithdraw() (owner only)
```

---

## Differentiator (one chart for all content)

```
                    변동성 높을 때 어떻게 하나?

Arrakis:     수수료를 올린다 (LP는 유지)      → IL에 여전히 노출
Gamma:       Range를 넓힌다 (LP는 유지)       → IL에 여전히 노출
Charm:       Range 리밸런싱 (LP는 유지)       → IL에 여전히 노출
Maverick:    LP가 알아서 판단                 → 수동, 전문가용
Yield Basis: 레버리지로 IL 상쇄               → 레버리지 리스크 추가

IL Alpha:    LP를 아예 끈다                   → IL 노출 = 0
```

---

## Tone & Style Guide

```
DO:
  ✅ 데이터로 말하기 (차트, 숫자, 온체인 증거)
  ✅ Caveat 솔직하게 ("백테스트 한계", "실전 미검증")
  ✅ 기술적 깊이 보여주기 (수학, 아키텍처)
  ✅ "왜 이렇게 만들었나" 설계 결정 공유
  ✅ 겸손하되 자신감 있게

DON'T:
  ❌ "곧 런칭!", "To the moon!", 가격 언급
  ❌ 날짜 확정 약속
  ❌ 다른 프로젝트 비난 (비교는 OK, 비난은 NO)
  ❌ 과대 약속 ("guaranteed returns" 등)
  ❌ 기술 모르는 척 (우리 강점은 기술 깊이)
```

---

## Content Calendar Template

```
매일 1트윗, 짧은 빌딩 로그 스타일:

  포맷:
  [Day N] IL Alpha Vault
  오늘 한 일: {1줄}
  {스크린샷 or 데이터 1개}
  #BuildInPublic #DeFi #UniswapV4

  주간 루틴:
  월: 기술 내용 (수학, 아키텍처, 설계 결정)
  화: 빌딩 로그 (오늘 뭐 했다)
  수: 업계 인사이트 (LP 통계, 경쟁사 분석)
  목: DAO 트레저리 분석 (특정 DAO 유휴 자산 분석, 거버넌스 포럼 포스트)
  금: testnet 주간 리포트 (성과 데이터, 대조군 비교)
  토/일: 자유 (QnA, 가벼운 내용, 쉬어도 됨)

  B2B 월간 루틴:
  1주차: DAO 트레저리 성과 비교 리포트 발행
  2주차: 타겟 DAO 거버넌스 포럼에 제안서 포스트 (1-2개)
  3주차: 기존 파트너 성과 업데이트
  4주차: 신규 DAO 리서치 + 아웃리치
```

---

## Related Documents
- [ROADMAP.md](./ROADMAP.md) — Full commercialization roadmap
- [COMPETITIVE.md](./COMPETITIVE.md) — Competitor analysis
- [../TODOS.md](../TODOS.md) — Implementation tasks
- [roadmap.html](./roadmap.html) — Visual roadmap (browser)
