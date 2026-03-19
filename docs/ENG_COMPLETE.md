# ENG Complete — Final Code (Post-Audit Fixes)

Date: 2026-03-20
Status: **CODE FREEZE. Audit findings resolved. Ready for deployment.**

---

## 최종 수치

- 75 tests | 0 failures
- Hook 31 + Vault 37 + Controls 7
- Audit: 38 findings → 20 code fixes applied, rest resolved/documented

---

## Audit 수정 요약

| 심각도 | 발견 | 수정 |
|--------|------|------|
| Critical | 4 | 4 ✅ |
| High | 8 | 7 ✅ (H-3 Phase 4) |
| Medium | 10 | 6 ✅ (나머지 이미 해결) |
| Low | 6 | 3 ✅ (나머지 이미 해결) |

### Critical 수정
- C-1: 출금수수료 실제 차감 (withdraw/redeem 오버라이드)
- C-2: mint() 가드 추가 (pause, cap, TWAP, reentrancy)
- C-3: setPoolKey LP 활성 시 차단
- C-4: twapThreshold 범위 [10, 2000]

### High 수정
- H-1: 실제 TWAP (10-observation sliding window)
- H-2: Slippage 보호 (maxSlippageBps 1%)
- H-4: pushVol rate limit 2x + zero cap 1e18
- H-5: withdraw/redeem nonReentrant
- H-6: AlwaysLP double-count 제거
- H-7: totalAssets asset 토큰만 계산
- H-8: 모든 admin setter 이벤트

### Medium 수정
- M-3: setLPRange tick spacing 정렬 검증
- M-4: afterInitialize lower == upper 방지
- M-6: SwapHelper reentrancy + safeTransferFrom

### Low 수정
- L-4: transferOwnership zero-address 차단
- L-5: setKeeper zero-address 차단
- L-6: claimFees 잔액 체크 + zero-address 차단

---

## 배포 준비

### Wallet 구성
```
Deployer:  0x035FD73BD1583BAF23264eEE954aeb8D35d74bC1
Operator:  0xbE61c1Fe3e6837d627200F46939173a88fe7fAA6
Treasury:  0x3d740198D9b9702fe27FaC80D6Bfa8704c438e46
Sentinel:  0x0b034b10d7bB219d4bbdbf5d241380693e3B4c9C
```

### 배포 명령어
```bash
export PRIVATE_KEY=0x...  # Deployer key
export RPC_URL=https://mainnet.base.org
cd contracts
forge script script/DeployBase.s.sol:DeployBase \
  --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast
```

### 배포 후 체크리스트
1. hook.setKeeper(Sentinel 주소)
2. vault.setKeeper(Sentinel 주소)
3. hook.transferOwnership(Gnosis Safe) → Safe에서 acceptOwnership
4. vault.transferOwnership(Gnosis Safe) → Safe에서 acceptOwnership
5. vault.deposit(seed USDC)
6. keeper bot 시작 (--rpc-url https://mainnet.base.org)

---

## 프론트엔드

- `app/index.html` — 지갑 연결 + deposit/withdraw
- Live: https://official-belta.github.io/il-alpha-site/app.html
- 배포 후 CONFIG.VAULT 주소 업데이트 필요

---

## Audit 대상 파일 (변경 금지)

```
contracts/src/ILAlphaHook.sol
contracts/src/ILAlphaVault.sol
contracts/src/BaseVault.sol
```
