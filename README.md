# offbit

## todos

- user_strategy

- strategy - 전략 코인이나 전략 코인 수정은 어드민 페이지에서 해야하는데 나중에 만들자.

- login

  1. 회원가입 email validation 추가
  2. 무차별 비밀번호 삽입 공격 대응
  3. 비밀번호 초기화 코드 무지성 삽입 공격 대응
  4. 보안코드시간 만료 다시 보내기 구현

- pages

  1. index
  2. 상품설명
  3. 공지사항
  4. 고객지원
  5. 회사소개
  6. 이용약관
  7. 개인정보처리방침
  8. 서비스문의
  9. 사업제휴
  10. 투자자 설명서

- 배포
  1. 비대칭 키 컨트롤
     서버에서 시작할 때 비대칭 키 있는지 확인하고 없으면 만들게.
     or config["secret_key"]로 비대칭 키 대신하기(비대칭키가 필요 없을 것 같음)

## did these

- user_strategy

  1. add coin selection.
     add coin selection at form
     show selected coin at dashboard list
     can be changed by 투자 설정

- investing

  1. 투자 시작과 동시에 컨디션에 따라 매수, 매도. 이후에는 execution_time에 맞춰서 진행 (done)
  2. 투자 진행 중일 경우, 설정 버튼을 지우고 거기에 매수 대기, 매수 대기 현금 혹은 매도 대기, 매도 대기 수량 보여주기 (done)
  3. api 세팅할 때 ip 주소 입력하게하기 (done)
  4. api 연동할 때 연동 되었는지 테스트하기 -> 연동 안되었으면 취소 (done)

- strategy

  1. 비트코인 벤치마크 퍼포먼스 보여주기 매 시간 업데이트로 변경 (done)
  2. 전략 퍼포먼스 매 분 보여주는 것 매 시간 업데이트로 변경 (done)

  3. 퍼포먼스 sorting 구현 (done)
  4. 백테스트 보여주는 strategy 개별 페이지 구현. (done)
  5. 개별 페이지에서 투자 성능 지표 표로 보여주기 (done)
     1. 총수익률
     2. 연복리수익률
     3. MDD
     4. 투자 성공률(승률)
     5. 손익비
     6. 시장 참여 비율
  6. ma 전략 하나 만들어서 올리기 (done)
  7. 전략 만들기는 어드민만 보이게 하기. (done)
