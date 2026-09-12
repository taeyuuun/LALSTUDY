# 홈 화면 직접 수정하기 — Python 몰라도 됨

이제 홈 화면 문구는 `app.py`가 아니라:

`HOME_CONTENT.toml`

만 수정하면 됩니다.

## 가장 자주 바꿀 부분

```toml
[ko]
hero_title = "논문을 읽고,\nFigure를 이해하고,\n실험기법까지 연결하세요."
hero_subtitle = "여기에 설명"
paper_button = "📄 논문으로 시작하기"
method_button = "🧬 실험기법 찾아보기"
```

## 카드 문구

```toml
feature_1_title = "연구의 핵심 논리"
feature_1_text = "설명"

feature_2_title = "Figure 중심 학습"
feature_2_text = "설명"
```

## 섹션 자체를 숨기기

파일 위쪽:

```toml
[design]
show_feature_cards = true
show_start_flows = true
show_open_beta_note = true
```

`true`를 `false`로 바꾸면 해당 섹션이 사라집니다.

예:

```toml
show_start_flows = false
```

## 줄바꿈

제목 안에서 줄바꿈:

```toml
hero_title = "논문을 읽고,\nFigure를 이해하고,\n실험기법까지 연결하세요."
```

`\n`이 줄바꿈입니다.

## 수정 후

로컬 Streamlit이 켜져 있으면 저장만 해도 다시 반영됩니다.

GitHub에 올릴 때:

```powershell
git add HOME_CONTENT.toml app.py
git commit -m "Update home content"
git push
```

## 주의

가급적 `=` 왼쪽 변수 이름은 바꾸지 말고,
`"..."` 안의 문구만 수정하세요.
