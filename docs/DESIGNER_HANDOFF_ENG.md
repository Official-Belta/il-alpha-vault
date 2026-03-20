# Designer → ENG Handoff: Vault 페이지 Web3 연동 검증 요청

Date: 2026-03-21
From: Designer terminal
To: Keeper ENG / Contract ENG

---

## 요약

Vault 페이지(`docs/milestone/vault.html`)에 ethers.js v6 기반 Web3 연동 완료.
**ENG 검증 후 VAULT_ADDRESS만 교체하면 라이브.**

---

## 1. CONFIG 검증 (vault.html 상단)

```javascript
const CHAIN_ID = 42161;                                              // Arbitrum One
const RPC_URL = 'https://arb1.arbitrum.io/rpc';                      // Public RPC (read-only)
const VAULT_ADDRESS = '0x0000000000000000000000000000000000000000';   // ← 배포 후 교체
const USDC_ADDRESS = '0xaf88d065e77c8cC2239327C5EDb3A432268e5831';   // Arbitrum native USDC
const EXPLORER = 'https://arbiscan.io';
```

**ENG 확인:**
- [ ] USDC 주소 맞는지 (Arbitrum native USDC, 6 decimals)
- [ ] Public RPC rate limit 괜찮은지 (30초 간격 호출)
- [ ] Alchemy/Infura 키 필요하면 알려줘 → `RPC_URL` 교체

---

## 2. ABI 검증

```javascript
const VAULT_ABI = [
  'function deposit(uint256 assets, address receiver) external returns (uint256)',
  'function withdraw(uint256 assets, address receiver, address owner) external returns (uint256)',
  'function totalAssets() external view returns (uint256)',
  'function balanceOf(address) external view returns (uint256)',
  'function convertToShares(uint256 assets) external view returns (uint256)',
  'function convertToAssets(uint256 shares) external view returns (uint256)',
  'function maxDeposit(address) external view returns (uint256)',
  'function depositCap() external view returns (uint256)',
  'function paused() external view returns (bool)',
  'function getVaultMetrics() external view returns (uint256,uint256,uint256,uint128,uint256,bool,bool)',
  'function UNAUDITED() external view returns (bool)'
];
```

**ENG 확인:**
- [ ] `getVaultMetrics()` 리턴 순서: `(totalAssets, idle, deployed, deployedLiquidity, sharePrice, lpActive, isPaused)` 맞는지
- [ ] `sharePrice` = `metrics[4]` → USDC 6 decimals 기준 `Number(metrics[4]) / 1e6` 맞는지
- [ ] `maxDeposit(address)` — 아무 주소 넣어도 같은 값 리턴하는지 (public read에서 `maxDeposit(VAULT_ADDRESS)` 호출 중)

---

## 3. 데이터 흐름 (2단계)

### Stage 1: 페이지 로드 (지갑 없이)
```
initPublicRead()
  → JsonRpcProvider(RPC_URL)             // public read-only
  → vaultRead.getVaultMetrics()          // TVL, Share Price, LP Status
  → vaultRead.maxDeposit(VAULT_ADDRESS)  // 잔여 캡
  → 30초마다 자동 갱신
```
**결과:** 지갑 연결 없이도 볼트 현황 실시간 표시

### Stage 2: 지갑 연결 (입출금 시)
```
connectWallet()
  → BrowserProvider(window.ethereum)
  → chain 42161 확인 (아니면 자동 전환)
  → signer 생성
  → usdcWrite.balanceOf(user)     // USDC 잔액
  → vaultWrite.balanceOf(user)    // 보유 셰어
  → deposit/withdraw 활성화
```

### Deposit 플로우
```
doDeposit(amount)
  → parseUnits(amount, 6)                    // USDC 6 decimals
  → usdcWrite.allowance(user, VAULT)         // approve 체크
  → if 부족: usdcWrite.approve(VAULT, MaxUint256)
  → vaultWrite.deposit(assets, user)
  → TX 대기 → Arbiscan 링크 표시
```

### Withdraw 플로우
```
doWithdraw(amount)
  → parseUnits(amount, 6)
  → vaultWrite.withdraw(assets, user, user)
  → TX 대기 → Arbiscan 링크 표시
```

---

## 4. 미배포 상태 (현재)

`VAULT_ADDRESS === '0x000...000'` 감지 시:
- Public read: 메트릭에 "Deploying..." 표시
- Wallet connect: USDC 잔액만 조회 (readProvider 경유)
- Deposit/Withdraw 버튼 비활성화
- **에러 없음**

**배포 후:** VAULT_ADDRESS 한 줄만 교체 → 즉시 작동

---

## 5. ENG 검토 요청

| # | 항목 | 질문 |
|---|------|------|
| 1 | `approve(MaxUint256)` | 무제한 approve — 일반 DeFi 패턴이지만 우리 vault에서 안전한지 |
| 2 | USDC decimals | `parseUnits(val, 6)` — Arbitrum USDC가 6 decimals 맞는지 |
| 3 | `withdraw(assets, receiver, owner)` | receiver와 owner 모두 user 본인 — 올바른 호출인지 |
| 4 | revert reason | ethers.js v6에서 vault revert message 제대로 표시되는지 |
| 5 | Public RPC | `arb1.arbitrum.io/rpc` — production 트래픽에 충분한지 |
| 6 | 추가 표시 데이터 | EWMA variance, 마지막 rebalance 시간 등 추가로 보여줄 게 있으면 |

---

## 6. 배포 후 디자이너에게 전달할 것

1. **VAULT_ADDRESS** — 실제 배포 주소
2. **작동 확인** — `getVaultMetrics()` public RPC 호출 결과 캡처
3. **RPC 추천** — public 유지 or 키 필요?
4. **추가 ABI** — vault 페이지에 표시할 추가 함수 있으면

---

## 파일 위치

```
docs/milestone/vault.html     ← 전체 vault 페이지 (HTML+CSS+JS 올인원)
docs/milestone/build.py       ← 메인 사이트 빌더
docs/milestone/roadmap.json   ← 로드맵 (Arbitrum 전환 완료)
```

**라이브:** `official-belta.github.io/il-alpha-site/vault.html`
