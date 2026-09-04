# 복구센터

디스코드 게임샵의 만료된 다운로드 링크 복구요청 사이트.

- 첫 화면: 관리자 로그인 / 유저 로그인 (디스코드 OAuth2)
- 유저: 지정 역할 보유자만 접근 가능 → 복구요청 접수, 내 요청 상태 확인
- 관리자: 요청 확인 → 링크 입력 → 봇이 유저 디스코드 DM으로 즉시 발송
- Python 표준 라이브러리만 사용 (WSGI 앱 `server:application`). 데이터: `data/recover.db`
- 요청 기록은 30일 후 자동 삭제

## 설정

1. `secrets_config.example.py` 를 `secrets_config.py` 로 복사하고 실제 값 입력
   (`secrets_config.py` 는 깃허브에 올라가지 않음)
2. 디스코드 개발자 포털 → 앱 → OAuth2 → Redirects 에 `<BASE_URL>/callback` 등록
   (예: `https://chhc.pythonanywhere.com/callback`)

## 로컬 실행

```
python server.py        # http://localhost:8080
```

## PythonAnywhere 배포

1. Bash: `git clone https://github.com/<아이디>/recover.git`
2. Files 탭에서 `secrets_config.py` 를 `/home/<아이디>/recover/` 에 업로드
3. Web 탭: Source code = `/home/<아이디>/recover`,
   WSGI 파일을 아래 3줄로 교체 후 Reload:
   ```python
   import sys
   sys.path.insert(0, "/home/<아이디>/recover")
   from server import application
   ```

코드 갱신: Bash `cd ~/recover && git pull` → Web 탭 Reload
