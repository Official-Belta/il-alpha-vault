# ENG Complete — Code Freeze v2

Date: 2026-03-20
Status: **CODE FREEZE. 컨트랙트 코드 변경 없음.**

---

## 최종 수치

- 77 tests | 0 failures
- Hook 31 + Vault 37 + Controls 9
- Gas: swap with hook = 538K

---

## CEO 인계 사항

### 즉시 필요
1. **Base mainnet 지갑 생성** — 새 EOA (배포용)
2. **$1.2K seed** — Base USDC ($400 × 3 vaults)
3. **Gnosis Safe 생성** — Base mainnet, 2/3 multi-sig 권장
4. **Keeper 지갑** — 배포 지갑과 분리된 별도 EOA + ~0.01 ETH

### 배포 시 ENG에게 전달
- 배포 지갑 private key
- Keeper 지갑 private key
- Gnosis Safe 주소

### 배포 후 CEO 작업
- UFSF 감사 신청 (코드 프리즈 확인됨, mainnet 주소 첨부)
- DAO 아웃리치 시작 (mainnet 2-4주 데이터 후)
- Litepaper 작성 (최종 아키텍처 확정됨)

---

## 디자이너 인계 사항

### 대시보드 Base 전환
- `docs/dashboard/index.html` — 현재 Sepolia 기준
- CSV fetch URL을 Base mainnet 데이터로 변경
- 또는 실시간 fetch: `https://raw.githubusercontent.com/Official-Belta/il-alpha-vault/master/keeper/metrics.csv`

### UNAUDITED 배너
- 사이트 전체에 "UNAUDITED — USE AT OWN RISK" 고지 배너 추가
- 컨트랙트에 `UNAUDITED = true` 상수 있음 — 프론트에서 읽어서 표시 가능

### Etherscan 링크
- 현재 Sepolia 링크 → Base mainnet으로 교체
- `docs/milestone/roadmap.json`의 `etherscan_base` 필드 업데이트

---

## 코드 프리즈 범위

**변경 금지 (audit 대상):**
```
contracts/src/ILAlphaHook.sol
contracts/src/ILAlphaVault.sol
contracts/src/BaseVault.sol
```

**변경 가능 (audit 비대상):**
```
contracts/script/*        — 배포 스크립트
contracts/src/controls/*  — 대조군 vault
contracts/src/SwapHelper.sol — 테스트넷 헬퍼
keeper/*                  — Python keeper bot
docs/*                    — 문서/사이트
```

---

## Known Items (감사자 전달용)

1. TWAP 체크가 hook lastTick 기반 (진짜 TWAP 아님) — 보수적 threshold로 완화
2. Withdrawal fee가 회계 기록만 (실제 토큰 차감 아님) — 감사자 의견 필요
3. totalAssets()가 slot0 기반 — 같은 블록 조작 가능, TWAP 체크로 완화
4. 50/50 split LP — Phase 4에서 단일자산 입금으로 개선 예정
5. rebalance()는 public — 누가 호출해도 결과 동일 (hook 신호 기반)
