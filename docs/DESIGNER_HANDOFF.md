# Designer Handoff — Roadmap Site Update

Date: 2026-03-20
From: CEO session
Reference: docs/ROADMAP.md (최신 버전)

---

## 작업: roadmap.json 업데이트 → build.py 실행 → index.html 재생성

DESIGN.md 기준 유지. 모든 변경에 i18n.ko 동기화.

---

## 1. project 객체 수정

```json
{
  "description": "Treasury-grade LP management that removes positions before impermanent loss hits. Capital preservation with LP-level returns."
}
```

한국어:
```
"비영구적 손실이 발생하기 전에 LP 포지션을 제거하는 트레저리급 LP 관리. LP 수준의 수익률과 자본 보전."
```

tagline은 유지: "Volatility-aware liquidity management"

---

## 2. Phase 변경 매핑

| 기존 | 변경 후 | status |
|------|--------|--------|
| 01 Backtest | 유지 | complete |
| 02 Smart Contracts | 유지 | complete |
| 03 Testnet Validation | 유지 | **complete** (기존 active → complete) |
| 04 Mainnet | **Base Mainnet** | **active** |
| 05 Growth | **Grants & Audit** | upcoming |
| 06 Moat Building | **DAO GTM** | upcoming |
| 07 Governance | **Moat** | upcoming |
| 08 Multi-Chain | **Governance** | upcoming |
| 09 Institutional | 유지 or 삭제 | upcoming |

---

## 3. 각 Phase 상세

### Phase 03 — Testnet Validation → **complete**
```json
{
  "status": "complete",
  "description": "Three vaults deployed to Sepolia. Keeper bot live. 4-round Trail of Bits security audit: 0 Critical, 0 High. Dashboard operational."
}
```
한국어: "3개 볼트 Sepolia 배포. 키퍼 봇 가동. 4라운드 Trail of Bits 보안 감사: Critical 0, High 0. 대시보드 운영 중."

기존 items에 추가:
- { "text": "4-round Trail of Bits security audit — 0 Critical, 0 High", "status": "done" }
- { "text": "Performance dashboard live (Chart.js)", "status": "done" }

### Phase 04 — Base Mainnet (active)
```json
{
  "number": "04",
  "name": "Base Mainnet",
  "status": "active",
  "description": "Code freeze complete. Deploying to Base mainnet with $1.2K seed capital. 4-week live operation for real performance data.",
  "items": [
    { "text": "Code freeze — all features complete, 4-round audit clean", "status": "done" },
    { "text": "Wallet setup (Deployer, Operator, Treasury Safe, Sentinel)", "status": "done" },
    { "text": "Deploy 5 contracts to Base mainnet", "status": "active" },
    { "text": "Seed $400×3 vaults on real ETH/USDC pool", "status": "pending" },
    { "text": "Keeper bot live on Base (1hr cycles)", "status": "pending" },
    { "text": "Dashboard update — real mainnet data", "status": "pending" },
    { "text": "4-week live performance monitoring", "status": "pending" }
  ]
}
```
한국어:
- name: "Base 메인넷"
- description: "코드 프리즈 완료. $1.2K 시드로 Base 메인넷 배포. 4주 실운영으로 실제 성과 데이터 확보."
- items 각각 번역

### Phase 05 — Grants & Audit (upcoming)
```json
{
  "number": "05",
  "name": "Grants & Audit",
  "status": "upcoming",
  "description": "UFSF audit subsidy application (up to 100% coverage). Hook Design Lab Cohort 2. Professional security audit on frozen code.",
  "items": [
    { "text": "UFSF audit subsidy application (Uniswap Foundation Security Fund)", "status": "pending" },
    { "text": "Hook Design Lab Cohort 2 application", "status": "pending" },
    { "text": "v4 Hooks Support application", "status": "pending" },
    { "text": "Professional security audit on code-frozen contracts", "status": "pending" },
    { "text": "Litepaper publication (5-8 pages)", "status": "pending" }
  ]
}
```
한국어:
- name: "그랜트 & 감사"
- description: "UFSF 감사 보조금 신청 (최대 100% 커버). Hook Design Lab 코호트 2. 코드 프리즈 상태에서 전문 보안 감사."

### Phase 06 — DAO GTM (upcoming)
```json
{
  "number": "06",
  "name": "DAO GTM",
  "status": "upcoming",
  "description": "DAO treasury acquisition as primary go-to-market. 3-5 partnerships at $1-2M each. Governance proposals with real mainnet performance data.",
  "items": [
    { "text": "Gnosis DAO governance proposal (new treasury manager seeking yield)", "status": "pending" },
    { "text": "ENS DAO outreach (active treasury forum, karpatkey managed)", "status": "pending" },
    { "text": "Polygon treasury proposal ($1.3B idle stablecoins)", "status": "pending" },
    { "text": "First DAO partnership closed ($1M+ TVL)", "status": "pending" },
    { "text": "Case study published → pitch next 4 DAOs", "status": "pending" },
    { "text": "Multi-pool expansion: wstETH/ETH, USDC/USDT", "status": "pending" }
  ]
}
```
한국어:
- name: "DAO GTM"
- description: "DAO 트레저리 확보가 핵심 GTM. 3-5개 파트너십 × $1-2M. 실제 메인넷 성과 데이터로 거버넌스 제안."

### Phase 07 — Moat (upcoming)
```json
{
  "number": "07",
  "name": "Moat",
  "status": "upcoming",
  "description": "Rehypothecation for idle capital yield. Vault share composability with lending protocols. Data advantage from runtime. V4 hook ecosystem first-mover.",
  "items": [
    { "text": "Rehypothecation: LP OFF idle funds → Aave/Compound yield", "status": "pending" },
    { "text": "Share composability: vault share as collateral on Morpho/Euler", "status": "pending" },
    { "text": "Data moat: longer runtime = more accurate vol oracle", "status": "pending" },
    { "text": "Custom vol models beyond EWMA (implied vol, ML prediction)", "status": "pending" },
    { "text": "Continuous audit + unbroken runtime as trust signal", "status": "pending" }
  ]
}
```
한국어:
- name: "해자 구축"
- description: "유휴 자본 재활용(rehypothecation). 렌딩 프로토콜과 vault share 결합. 런타임 데이터 우위. V4 훅 생태계 선점."

### Phase 08 — Governance (upcoming)
```json
{
  "number": "08",
  "name": "Governance",
  "status": "upcoming",
  "description": "Token decision only after PMF confirmed and TVL exceeds $5M. Pure revenue model until then.",
  "items": [
    { "text": "PMF confirmation: TVL $5M+, 10+ external depositors, 6mo+ no incidents", "status": "pending" },
    { "text": "Token vs no-token decision", "status": "pending" },
    { "text": "If token: community participation, flywheel, liquidity bootstrap", "status": "pending" },
    { "text": "If no token: pure revenue model, simpler regulatory path", "status": "pending" }
  ]
}
```
한국어:
- name: "거버넌스"
- description: "PMF 확인 및 TVL $5M 초과 후에만 토큰 결정. 그전까지 순수 수익 모델."

### Phase 09 — Multi-Chain (유지)
기존 그대로.

---

## 4. i18n.ko 업데이트 필요한 키

모든 phase name, description, items에 대응하는 한국어 번역 추가/수정.
특히 새로 추가된:
- "Grants & Audit" 관련 items
- "DAO GTM" 관련 items (Gnosis, ENS, Polygon 등)
- "Moat" 관련 items (rehypothecation, composability 등)
- "4-round Trail of Bits security audit" 번역

---

## 5. 빌드 & 검증

1. `python3 docs/milestone/build.py` 실행
2. index.html에서 Phase 3 = complete, Phase 4 = active 확인
3. 한국어 전환 시 모든 새 텍스트 번역 확인
4. DESIGN.md 기준 (Wall Street/Blackstone 미학) 유지 확인
