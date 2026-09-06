# -*- coding: utf-8 -*-
"""
비밀 설정 템플릿.
이 파일을 secrets_config.py 로 복사해서 실제 값을 채우세요.
secrets_config.py 는 .gitignore 에 있어 깃허브에 올라가지 않습니다.
"""

# 디스코드 개발자 포털 → 앱 → OAuth2
CLIENT_ID = "디스코드 앱 클라이언트 ID"
CLIENT_SECRET = "디스코드 앱 클라이언트 시크릿"

# 봇 토큰 (DM 발송·역할 확인에 사용)
BOT_TOKEN = "봇 토큰"

# 관리자 디스코드 ID 목록 (숫자)
ADMIN_IDS = [123456789012345678]

# 디스코드 서버(길드) ID
GUILD_ID = 123456789012345678

# 유저 로그인에 필요한 역할 ID (이 역할이 없으면 접근 거부)
USER_ROLE_ID = 123456789012345678

# 사이트 주소 — 디스코드 OAuth2 Redirects 에 "<BASE_URL>/callback" 등록 필요
BASE_URL = "https://chhc.pythonanywhere.com"

# 봇<->웹 동기화 인증키 — 아무 긴 랜덤 문자열. coinbot\websync.py 의 SYNC_KEY 와 동일해야 함
SYNC_KEY = "랜덤한 긴 문자열"
