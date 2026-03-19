# ENG Handoff — B2B Pivot + Mainnet 직행 + 코드 프리즈 → 감사

Date: 2026-03-20 (v3)
From: CEO session (Claude terminal)

---

## 🔴 최우선: 전체 실행 순서

```
1단계: 코드 프리즈까지 모든 기능 구현 완료     ← ENG 지금 해야 할 것
2단계: Base mainnet 배포 ($1.2K 시드, $400×3)
3단계: 2-4주 실운영 (본인 자금, 전체 시스템 E2E)
4단계: 코드 프리즈 확인 → UFSF 감사 신청       ← CEO가 신청
5단계: 감사 완료 → 캡 열고 외부 deposit
```

**핵심 원칙:** 감사는 최종 코드에 받는 것. 감사 후 코드 변경 = 감사 무효화 = 돈 낭비. 따라서 **감사 전에 모든 기능이 완성**되어야 함.

---

## 1단계: 코드 프리즈까지 남은 ENG 작업

### ✅ 완료된 작업
- [x] Share 회계 실시간 반영 (real-time LP valuation)
- [x] TWAP 체크 (deposit/withdraw 조작 방지)
- [x] 출금 수수료 0.1%
- [x] 볼륨 스파이크 트리거
- [x] 테스트넷 대시보드 (Chart.js)
- [x] 65 Solidity tests (fuzz 포함) 전부 통과

### 🔴 미완료 — 코드 프리즈 전 필수

| # | 작업 | 설명 | 우선순위 |
|---|------|------|---------|
| 1 | **멀티풀 지원** | wstETH/ETH, USDC/USDT 풀 추가. 단일 vault가 여러 풀 지원 or 풀별 vault | P0 |
| 2 | **Deposit 캡 하드코딩** | `maxTotalAssets` 파라미터. owner가 설정. 캡 초과 시 revert | P0 |
| 3 | **Unaudited 고지** | 컨트랙트에 `UNAUDITED` 상수/이벤트. 프론트엔드 배너 | P1 |
| 4 | **Base mainnet 배포 스크립트** | forge script, Base RPC, CREATE2 주소 마이닝 | P0 |
| 5 | **Keeper Base 전환** | Base RPC, 실제 ETH/USDC pool 연결, 1시간 주기 | P0 |
| 6 | **대시보드 Base 전환** | Sepolia → Base mainnet 데이터. Etherscan 링크 Base로 | P1 |
| 7 | **Public rebalance() 유지 + 검증** | CEO 결정: keeper-only 아님. 누구나 호출 가능해야 함 (탈중앙 + keeper 장애 안전장치). keeper-only 제한 롤백 필요. E2E 테스트. | P0 |
| 10 | **🔴 Withdrawal fee 완전 제거** | CEO+Audit 결정: fee 로직이 ERC-4626 스펙과 충돌하여 3라운드째 새 버그 생성 중. withdrawalFeeBps, accumulatedFees, claimFees(), setWithdrawalFeeBps(), beforeWithdraw fee 로직 전부 삭제. 감사 후 별도 모듈로 재추가. | P0 |
| 8 | **Emergency withdraw E2E 테스트** | owner가 긴급 인출 → LP 회수 → pause 플로우 검증 | P1 |
| 9 | **Gas 벤치마크** | vanilla V4 swap vs IL Alpha hook swap 가스 비교. 그랜트 신청에 필요 | P1 |

### 코드 프리즈 기준
- 위 9개 항목 전부 완료
- 모든 테스트 통과
- 더 이상 컨트랙트 코드 변경 없음
- ENG이 "코드 프리즈"라고 CEO에 보고

---

## 2단계: Base Mainnet 배포

**CEO 결정: Testnet 시뮬레이션 대신 Mainnet 직행.**

이유:
- 테스트넷 인위적 데이터는 DAO/그랜트 설득 불가
- "코드 작동"은 이미 검증됨 (65 tests + Sepolia)
- 진짜 ETH/USDC pool, 진짜 swap volume, 진짜 IL 데이터가 필요
- Charm도 감사 전 캡 걸고 런칭 — 우리도 같은 전략

**배포 사항:**

1. **체인: Base** (가스 저렴, V4 활성, UF와 궁합)

2. **컨트랙트 배포 (최신 코드, 코드 프리즈 후)**
   - ILAlphaHook (afterSwap vol oracle + volume spike trigger)
   - ILAlphaVault (real-time LP valuation + TWAP check + withdrawal fee + deposit cap)
   - AlwaysLPVault + HODLVault (대조군)
   - SwapHelper (keeper용)

3. **시드: CEO 자금 $1.2K**
   - 3개 vault에 $400씩 동일 배분
   - 외부 deposit 캡: 비활성화 (본인 자금만)
   - 참고: fee share 극히 작을 수 있음. TVL 작은 풀 고려 or 메이저 풀에서 % 기반 증명

4. **Keeper 재설정**
   - Base RPC로 전환
   - 실제 ETH/USDC pool에 연결
   - 1시간 주기 유지

5. **Unaudited 고지**
   - 사이트에 "UNAUDITED — USE AT OWN RISK" 배너
   - deposit 캡 하드코딩

6. **대시보드 업데이트**
   - Sepolia → Base mainnet 데이터로 전환
   - 실제 성과 데이터 표시

---

## 3단계: 2-4주 실운영

- 본인 자금 $400×3으로 전체 시스템 E2E 검증
- Keeper 안정성, vol oracle 정확도, LP 토글 정상 작동 확인
- 실제 성과 데이터 축적 → 그랜트 신청 + DAO 아웃리치 근거
- 이 기간에 코드 변경 없음 (버그 발견 시 코드 프리즈 해제 → 수정 → 재프리즈)

---

## 4단계: UFSF 감사 신청 (CEO 담당)

코드 프리즈 + mainnet 실운영 데이터 확보 후:
- UFSF (Uniswap Foundation Security Fund) 감사 보조금 신청
- 감사비 최대 100% 커버 가능 ($80K+ 절약)
- 신청: https://areta.fillout.com/UFSF
- 필요: 최종 코드, 테스트 커버리지, mainnet 주소, 실운영 데이터

---

## 참고: B2B 피봇 완료 (메시징만, 코드 변경 없음)

타겟이 **B2C (개인 LP) → B2B (DAO 트레저리)**로 변경됨.

변경된 파일 (모두 메시징/문서):
- `docs/MESSAGING.md` — DAO 1순위, B2B 피치 섹션 추가
- `docs/COMPETITIVE.md` — "B2C gap" → "DAO Treasury gap"
- `docs/ROADMAP.md` — Phase 5 = DAO GTM, 재무 전망 수정
- `docs/milestone/thesis.html` — Hero, Problem, Backtest 전면 B2B 리프레임
- `docs/milestone/roadmap.json` — description, Phase 05, i18n
- `docs/milestone/index.html` — build.py 재생성 완료

**컨트랙트/keeper/백테스트 코드 변경 없음.**

---

## 참고: CEO 진행 중 / 완료 작업

- ✅ 거버넌스 제안서 템플릿 (EN/KO) — `docs/governance-proposal-template*.md`
- ✅ DAO 타겟 리스트 20개 — `docs/dao-target-list.md`
- ✅ 그랜트 전략 — `docs/grant-strategy.md`
- ✅ UF 신청서 초안 — `docs/grants/uniswap-foundation-application.md`
- ⏳ Litepaper 초안 — 코드 프리즈 후 작성 (최종 아키텍처 반영)
- ⏳ UFSF 감사 신청 — 코드 프리즈 + mainnet 실운영 후
- ⏳ DAO 아웃리치 — mainnet 2-4주 데이터 후

---

## 결정 사항 요약

| 결정 | 내용 |
|------|------|
| Primary target | DAO 트레저리 (B2B) |
| 핵심 셀링 포인트 | Sharpe 3.66, Max DD -12%, perf-fee-only, ERC-4626 |
| 런칭 전략 | Charm 모델 — 캡 낮게, 감사 전 런칭, 성과로 증명 |
| 체인 | Base |
| 시드 | $1.2K ($400×3 vaults) |
| 감사 | UFSF 보조금 (코드 프리즈 후 신청) |
| 그랜트 | Hook Design Lab은 mainnet 데이터 후. UFSF 먼저. |
