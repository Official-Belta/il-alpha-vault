# Competitive Notes — Gemini Analysis (참고용)

Date: 2026-03-20
Source: Gemini competitive analysis + Bunni post-mortem
Status: 참고만. 현재 전략 변경 없음.

---

## 시장 경쟁 카테고리

| 카테고리 | 전략 | 대표 | IL Alpha 해당 |
|---------|------|------|-------------|
| LVR 관리형 | 차익거래 수익 LP 환원, 동적 수수료 | Bunni, Diamond | 부분적 |
| JIT 유동성 | 스왑 시에만 유동성 공급, 나머지는 렌딩 | Flashifi | 아님 |
| 자동 재밸런싱 | 범위 실시간 최적화 | Gamma, Arrakis | 아님 |
| **Binary LP Toggle** | LP 전체 on/off | **IL Alpha (유일)** | 우리 카테고리 |

## 시장의 "성공 공식" vs 우리

| 요소 | 시장 요구 | 우리 | 조치 시점 |
|------|----------|------|----------|
| Gas 최적화 (Singleton + Transient Storage) | 핵심 | 미확인 | 코드 프리즈 전 벤치마크 |
| MEV 포착 (Backrun → LP 환원) | 필수급 | 없음 | Phase 6+ |
| Re-hypothecation (유휴 자금 재활용) | 중요 | 없음 (LP OFF 시 자금 유휴) | Phase 5-6 |
| ERC-6909 | 트렌드 | 안 씀 (ERC-4626) | 멀티풀 시 검토 |
| Flywheel / 생태계 결합성 | 생존 결정 | 없음 | 12-18개월 후 |

## Bunni 사망 교훈

1. "손실 줄여준다"만으로 LP 안 움직임 → 추가 인센티브 필요
2. 리밸런싱 가스비 > 수익이면 의미 없음
3. 기술만으로 안 됨. "누가 share를 담보로 받아주나"가 생존 결정

## 우리 대응 (장기 로드맵 참고)

- 6개월 후: share 담보 통합 (Morpho, Euler 등)
- 12개월 후: rehypothecation (LP OFF 시 → Aave)
- 18개월 후: Flywheel 구축 (토큰/bribe 검토)

## 결론

지금 이것들 구현하면 Bunni처럼 복잡해져서 죽음.
단순하게 런칭 → 생존 → 점진적 추가가 맞음.
