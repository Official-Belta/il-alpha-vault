# ENG Status — Base Mainnet Ready

Date: 2026-03-20
From: ENG session

---

## CEO Handoff 완료

| 우선순위 | 항목 | 상태 |
|---|---|---|
| 🔴 P0 | Share 회계 버그 | ✅ 실시간 LP 가치 + TWAP 체크 + 출금 수수료 0.1% |
| 🟡 P1 | 성과 대시보드 | ✅ Chart.js, 디자이너에게 스타일 핸드오프 |
| 🟢 P2 | 볼륨 스파이크 트리거 | ✅ 3x EWMA → 쿨다운 무시 긴급 LP OFF |

---

## Testnet 평가 결론

**검증 완료:** 코드 작동 (배포, 연결, 호출, LP 배포/회수, keeper 파이프라인)
**검증 불가:** 전략 수익성 (testnet에 실제 swap volume/fee/IL 없음)

→ Testnet에서 인위적 데이터 만드는 건 시간 낭비. Mainnet 직행 권장.

---

## Base Mainnet 배포 준비 완료

**확인 사항:**
- V4 PoolManager: `0x498581fF718922c3f8e6A244956aF099B2652b2b` (Base mainnet, 검증됨)
- 배포 스크립트: `contracts/script/DeployBase.s.sol`
- 대상 pool: USDC/WETH, 0.3% fee, 60 tick spacing
- 배포 비용: ~$0.05 (Base 가스 0.006 gwei)
- 실제 토큰: USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, WETH `0x4200000000000000000000000000000000000006`

**CEO 결정 필요:**
1. Base mainnet 지갑 (private key) — 새로 만들까, 기존 사용할까
2. $10K USDC seed 자금 준비 시점
3. Cap 설정 (Charm 모델: 초기 cap 낮게)
4. Keeper 지갑 분리 여부 (배포자 ≠ keeper 권장)

**배포 명령어 (지갑 준비되면 즉시 실행):**
```bash
export PRIVATE_KEY=0x...
export RPC_URL=https://mainnet.base.org
cd contracts
forge script script/DeployBase.s.sol:DeployBase \
  --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast
```

---

## 현재 코드 상태

- 65 tests passing (hook 31 + vault 25 + controls 9)
- P0 수정 포함 (실시간 LP 가치, TWAP, 출금 수수료)
- P2 수정 포함 (볼륨 스파이크 트리거)
- Sepolia testnet keeper 가동 중 (PID 101521)
- metrics.csv 20+ 사이클 데이터 수집 중

---

## 배포 후 즉시 해야 할 것

1. `vault.deposit(USDC_AMOUNT, deployerAddress)` — seed LP 입금
2. `hook.setKeeper(keeperAddress)` — keeper 지갑 설정
3. keeper bot 시작: `--rpc-url https://mainnet.base.org`
4. 대시보드 URL 공유 (DAO 아웃리치용)
