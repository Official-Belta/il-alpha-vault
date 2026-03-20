# Designer Handoff — ENG Session 2026-03-21

## 핵심: Base → Arbitrum 전환

### app/index.html (Vault UI)
```javascript
// 변경 필요
CHAIN_ID: 42161,              // was 8453
CHAIN_NAME: 'Arbitrum One',   // was 'Base'
RPC_URL: 'https://arb1.arbitrum.io/rpc',  // was mainnet.base.org
EXPLORER: 'https://arbiscan.io',          // was basescan.org
USDC: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',  // Arbitrum USDC
VAULT: '배포 후 업데이트',
```

### 대시보드
1. 데이터: Sepolia → Arbitrum mainnet
2. 대조군: 실배포 아님 → 시뮬레이션 ("simulated benchmark" 라벨)
3. TVL: $1M 전까지 숨김. 대신 표시:
   - LP ON/OFF 상태
   - Vol oracle 수치
   - 3-전략 수익률 비교 (%)
   - 운영 일수 + 사이클 수
4. 링크: Arbiscan

### milestone 사이트
- etherscan_base URL → `https://arbiscan.io`
- 체인명 Arbitrum으로

### UNAUDITED 배너
- 유지. 절대 제거 금지.

---

## 최종 코드 상태
```
Commit: 83b06c7 | 71 tests | C:0 H:0 | SHIP ✅
```

Hook/Vault 주소: 배포 후 ENG이 전달
