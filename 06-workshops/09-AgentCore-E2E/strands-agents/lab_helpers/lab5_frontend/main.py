import json
import os
import sys
import time
import uuid

import streamlit as st
from chat import ChatManager, invoke_endpoint_streaming
from chat_utils import make_urls_clickable
from streamlit_cognito_auth import CognitoAuthenticator

# 현재 파일의 디렉터리를 가져와 프로젝트 루트를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

from utils import get_customer_support_secret  # noqa: E402

secret = get_customer_support_secret()
secret = json.loads(secret)

authenticator = CognitoAuthenticator(
    pool_id=secret["pool_id"],
    app_client_id=secret["client_id"],
    app_client_secret=secret["client_secret"],
    use_cookies=False,
)

is_logged_in = authenticator.login()
if not is_logged_in:
    st.stop()


def logout():
    print("Logout in example")
    authenticator.logout()


CONTEXT_WINDOW = 10  # 컨텍스트에 포함할 대화 턴 수(사용자+어시스턴트 쌍)
qualifier = "DEFAULT"


def build_context(messages, context_window=CONTEXT_WINDOW):
    # 마지막 context_window*2개 메시지(사용자+어시스턴트 쌍)만 사용
    history = messages[-context_window * 2 :] if len(messages) > context_window * 2 else messages
    context = ""
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        context += f"{role}: {msg['content']}\n"
    return context


def format_response_text(text):
    """따옴표와 줄 바꿈의 이스케이프를 해제해 응답 텍스트의 형식을 지정한다."""
    if not text:
        return text

    # 바깥쪽 따옴표가 있으면 제거
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]

    # 일반적인 이스케이프 시퀀스 해제
    text = text.replace('\\"', '"')
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    text = text.replace("\\r", "\r")

    return text


with st.sidebar:
    st.text(f"Welcome,\n{authenticator.get_username()}")
    st.button("Logout", "logout_btn", on_click=logout)

st.title("Customer Support Agent")

chat_manager = ChatManager("default")

if "session_id" not in st.session_state:
    st.session_state["session_id"] = uuid.uuidv4()

# 채팅 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 앱 재실행 시 기록에 있는 채팅 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 받기
if prompt := st.chat_input("What is up?"):
    # 채팅 메시지 컨테이너에 사용자 메시지 표시
    with st.chat_message("user"):
        st.markdown(prompt)
    # 채팅 기록에 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    payload = json.dumps({"prompt": prompt, "actor_id": st.session_state["auth_username"]})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        import time

        start_time = time.time()
        accumulated_response = ""

        try:
            # 스트리밍 클라이언트 설정
            session_id = st.session_state.get("session_id")
            context = build_context(st.session_state.messages, CONTEXT_WINDOW)
            payload = json.dumps({"prompt": context})
            bearer_token = st.session_state.get("auth_access_token")

            # 맥동 애니메이션과 함께 초기 생각 중 상태 표시
            message_placeholder.markdown(
                '<span class="thinking-bubble">🤖 💭 Customer Support Agent is thinking...</span>',
                unsafe_allow_html=True,
            )

            # 애니메이션과 함께 응답 스트리밍
            chunk_count = 0
            formatted_response = ""

            for chunk in invoke_endpoint_streaming(
                agent_arn=st.session_state["agent_arn"],
                payload=payload,
                session_id=session_id,
                bearer_token=bearer_token,
                endpoint_name=qualifier,
            ):
                if chunk.strip():  # 비어 있지 않은 청크만 처리
                    accumulated_response += chunk
                    chunk_count += 1

                    # End 마커가 포함된 완전한 응답인지 확인(따옴표 버전)
                    if '"End agent execution"' in accumulated_response:
                        # 처리 중 상태 표시
                        message_placeholder.markdown(
                            '<span class="thinking-bubble">🤖 🔄 Processing response...</span>',
                            unsafe_allow_html=True,
                        )

                        # JSON을 파싱하고 형식이 지정된 응답 추출
                        try:
                            # 따옴표로 묶인 Begin 및 End 마커 사이의 JSON 부분 찾기
                            begin_marker = '"Begin agent execution"'
                            end_marker = '"End agent execution"'

                            begin_pos = accumulated_response.find(begin_marker)
                            end_pos = accumulated_response.find(end_marker)

                            if begin_pos != -1 and end_pos != -1:
                                # 마커 사이의 모든 내용 추출
                                json_part = accumulated_response[begin_pos + len(begin_marker) : end_pos].strip()

                                # JSON은 Begin 마커 바로 뒤에서 시작해야 함
                                json_start = json_part.find('{"role":')
                                if json_start != -1:
                                    json_str = json_part[json_start:]
                                    # 중괄호 개수를 세어 JSON 객체의 끝 찾기
                                    brace_count = 0
                                    json_end = -1
                                    for i, char in enumerate(json_str):
                                        if char == "{":
                                            brace_count += 1
                                        elif char == "}":
                                            brace_count -= 1
                                            if brace_count == 0:
                                                json_end = i + 1
                                                break

                                    if json_end != -1:
                                        json_str = json_str[:json_end]
                                        print(f"Extracted JSON: {json_str}")  # 디버그 출력
                                        response_data = json.loads(json_str)

                                        # JSON 구조에서 텍스트 추출
                                        if (
                                            "content" in response_data
                                            and len(response_data["content"]) > 0
                                            and "text" in response_data["content"][0]
                                        ):
                                            formatted_response = response_data["content"][0]["text"]
                                            print(f"Extracted text: {formatted_response}")  # 디버그 출력

                        except (json.JSONDecodeError, KeyError, IndexError) as e:
                            print(f"JSON parsing error: {e}")
                            print(f"Accumulated response: {accumulated_response}")
                            # 디버깅을 위해 전체 응답을 표시하는 대체 처리
                            formatted_response = accumulated_response
                        break

                    # JSON이 아닌 응답이나 누적 중인 스트리밍 텍스트 표시
                    else:
                        # 스트리밍 중 타이핑 커서 효과 추가
                        streaming_text = accumulated_response
                        if chunk_count % 3 == 0:  # 효과를 위해 몇 개 청크마다 커서 추가
                            streaming_text += ""

                        # 스트리밍 애니메이션으로 화면 업데이트(URL을 클릭 가능하게 변환)
                        clickable_streaming_text = make_urls_clickable(streaming_text)
                        message_placeholder.markdown(
                            f'<div class="assistant-bubble streaming typing-cursor">🤖 {clickable_streaming_text}</div>',
                            unsafe_allow_html=True,
                        )
                        # 스트리밍이 눈에 보이고 부드럽게 진행되도록 짧게 지연
                        time.sleep(0.02)

            # 소요 시간이 포함된 최종 응답(스트리밍 클래스 제거)
            elapsed = time.time() - start_time
            answer = (
                formatted_response
                if formatted_response
                else (accumulated_response if accumulated_response else "No response received")
            )

            # 이스케이프된 문자를 처리하도록 응답 형식 지정
            answer = format_response_text(answer)

            clickable_answer = make_urls_clickable(answer)
            message_placeholder.markdown(
                f'<div class="assistant-bubble">🤖 {clickable_answer}<br><span style="font-size:0.9em;color:#888;">⏱️ Response time: {elapsed:.2f} seconds</span></div>',
                unsafe_allow_html=True,
            )

        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            message_placeholder.markdown(
                f'<div class="assistant-bubble">🤖 ❌ {error_msg}</div>',
                unsafe_allow_html=True,
            )
            answer = error_msg
            elapsed = time.time() - start_time

        # 세션 상태에 최종 응답 추가
        final_answer = answer if "answer" in locals() else accumulated_response
        st.session_state.messages.append({"role": "assistant", "content": final_answer, "elapsed": elapsed})
        st.session_state["pending_assistant"] = False
        st.rerun()

        accumulated_response = chat_manager.invoke_endpoint_nostreaming(
            agent_arn=st.session_state["agent_arn"],
            payload=payload,
            bearer_token=st.session_state["auth_access_token"],
            session_id=st.session_state["session_id"],
        )

        print(f"Response: {accumulated_response}")
        # 채팅 기록에 어시스턴트 응답 추가
        st.session_state.messages.append({"role": "assistant", "content": accumulated_response})
