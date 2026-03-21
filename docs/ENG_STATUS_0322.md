# ENG Status — 2026-03-22

## 완료 작업

### #15 SwapHelper 배포 (P0)
- Arbitrum: `0xe09f9Ead03f315dc62AeBD56E5174fc72b42524B`
- Keeper에서 `--swap-helper` 플래그로 매시간 소액 swap → afterSwap hook 트리거

### #16 pushVolumeEstimate 구현 (P1)
- Hook에 `pushVolumeEstimate(PoolKey, uint128)` 추가
- Keeper가 Binance volume을 스케일링해서 push → LP 판단에 사용
- 2x rate limit 적용 (arb-v4 audit H-1 반영)
- **Hook 코드 변경 → 재배포 완료**

### Arbitrum 재배포 (v2)
```
ILAlphaHook:  0xbfC9E774e6b55C9a1bdA92e0AED946B4d0619040
ILAlphaVault: 0xa2e2748F021082F153f6B275fc3Ee601A5c7407F
SwapHelper:   0xe09f9Ead03f315dc62AeBD56E5174fc72b42524B

설정 완료:
✅ hook.setKeeper(0x0b034b10...Sentinel)
✅ vault.setKeeper(0x0b034b10...Sentinel)
✅ hook.setVault(0xa2e2...Vault)
```

### Arbiscan
- Hook: https://arbiscan.io/address/0xbfC9E774e6b55C9a1bdA92e0AED946B4d0619040
- Vault: https://arbiscan.io/address/0xa2e2748F021082F153f6B275fc3Ee601A5c7407F

---

## Keeper/디자이너 업데이트 필요

```
pool_key.json hooks → 0xbfC9E774e6b55C9a1bdA92e0AED946B4d0619040
vault.html VAULT    → 0xa2e2748F021082F153f6B275fc3Ee601A5c7407F
admin.html HOOK     → 0xbfC9E774e6b55C9a1bdA92e0AED946B4d0619040
admin.html VAULT    → 0xa2e2748F021082F153f6B275fc3Ee601A5c7407F
```

---

## 다음 (CEO 결정)
1. Keeper 재시작 (새 주소 + --swap-helper)
2. Treasury에서 vault.deposit(USDC)
3. Owner → Gnosis Safe 이전
4. 재audit 결과 확인 후 최종 SHIP
