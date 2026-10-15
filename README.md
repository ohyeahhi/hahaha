# 동글마을

어른에게는 힐링, 아이에게는 배움(경제 → 영어)이 되는 동글동글한 마을 생활 게임입니다.

## 해보기

```bash
python3 -m http.server 8000
# 휴대폰이나 브라우저에서 http://localhost:8000/village/ 접속
```

- **땅 누르기:** 걸어가요. (키보드: 방향키 / WASD)
- **밭 누르기:** 씨앗 심기 → 물주기 → 수확
- **가게 누르기:** 오늘의 시세로 팔기, 씨앗 사기, 용돈기입장 보기
- **연못 누르기:** 낚시. `!` 가 뜨면 화면을 탭하세요.
- **집 누르기:** 저금통(하루 이자 5%), 잠자기(다음 날로 넘어가기)
- **EN 버튼:** 대화와 아이템 이름에 영어를 함께 보여줘요.

저장은 브라우저에 자동으로 돼요.

## 폴더

- `village/`: 동글마을 시제품 (한 파일, 외부 라이브러리 없음)
- `docs/기획서.md`: 지금까지 정한 내용과 다음 단계
- `docs/art-reference/`: 캐릭터 원본 그림
- `village/assets/dongle/`: 원본 그림에서 오려낸 동글이 캐릭터 (게임에서 사용)
- `tools/cutout.py`: 배경이 단색인 사진에서 캐릭터를 오려내는 도구
  (`python tools/cutout.py docs/art-reference/coffee.webp village/assets/dongle coffee 280`, OpenCV 필요)
- `prototypes/clay3d/`: 3D 찰흙 캐릭터 실험
- `prototypes/fox-run/`: 첫 시험용 점프 러너 (미니게임 후보)
