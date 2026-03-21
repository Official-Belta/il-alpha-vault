# Designer → ENG: 관리자 대시보드 연동 요청

Date: 2026-03-21
From: Designer

---

## 완료된 것

관리자 대시보드 (`admin.html`) 구현 완료. 한국어. 비공개 URL.

현재 on-chain 데이터 자동 조회 중:
- ✅ getVaultMetrics() → TVL, 셰어 가격, idle/deployed, LP 상태, paused
- ✅ depositCap(), maxDeposit() → 한도
- ✅ Transfer 이벤트 스캔 → 예치자 목록 + 잔액
- ✅ Deposit/Withdraw 이벤트 → 최근 입출금 기록
- ✅ Rebalanced 이벤트 → LP 진입/제거 기록, 마지막 리밸런스 시간
- ✅ 컨트랙트 배포 여부 확인 (getCode)
- ✅ Hook 배포 여부 확인

---

## ENG에게 필요한 것

### 1. KEEPER_ADDR (필수)

admin.html 상단에 빈 변수:
```javascript
const KEEPER_ADDR = ''; // ← 여기에 키퍼 EOA 주소
```

이거 채워주면 키퍼 ETH 잔액 모니터링 활성화됨:
- 0.05 ETH 미만 → 노란 경고
- 0.01 ETH 미만 → 빨간 위험

### 2. poolId (선택)

Hook의 `getVolEstimate(poolId)` 호출용. 현재 zero bytes32 넣고 있음.
실제 poolId 알려주면 변동성 데이터 정확하게 표시.

### 3. Rebalanced 이벤트 시그니처 확인

현재 가정:
```solidity
event Rebalanced(bytes32 indexed poolId, bool lpActive, uint128 liquidity)
```
실제 이벤트 시그니처가 다르면 알려줘. 안 맞으면 LP 진입/제거 기록이 안 잡힘.

### 4. 키퍼 생존 확인 방법

현재는 Rebalanced 이벤트 마지막 블록으로 "X분 전" 표시.
2시간 넘으면 경고.

더 정확한 방법 있으면 제안:
- heartbeat TX?
- keeper 상태 API?
- 별도 on-chain ping?

---

## 파일 위치

```
docs/milestone/admin.html  — 관리자 대시보드 (전체 코드)
```

접속: `official-belta.github.io/il-alpha-site/admin.html`
네비에 없음. 직접 URL만.

---

## 변경 방법

ENG가 직접 admin.html 수정해도 되고, 주소/값만 알려주면 디자이너가 반영.
