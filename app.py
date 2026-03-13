# ssh -T git@github.com
# python app.py
# !pip install slack-bolt==1.18.1
# !pip install tiktoken==0.5.2
# !pip install langchain-community==0.0.30
# !pip install langchain-openai==0.0.8
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
# from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from momento import CacheClient, Configurations, CredentialProvider
from langchain_community.chat_message_histories import MomentoChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from datetime import timedelta
from dotenv import load_dotenv
from slack_bolt import App
from typing import Any
import logging
import json
import time
import os
import re


CHAT_UPDATE_INTERVAL_SEC = 1


load_dotenv()


SlackRequestHandler.clear_all_log_handlers()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# 봇 토큰과 소켓 모드 핸들러를 사용하여 앱을 초기화
# app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    token=os.environ["SLACK_BOT_TOKEN"],
    process_before_response=True
)


class SlackStreamingCallbackHandler(BaseCallbackHandler):
    
    last_send_time = time.time()
    message = ""
    
    def __init__(self, channel, ts):
        self.channel = channel
        self.ts = ts
        self.interval = CHAT_UPDATE_INTERVAL_SEC
        # 게시글을 업데이트한 누적 횟수 카운터
        self.update_count = 0
        
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.message += token
        
        now = time.time()
        if now - self.last_send_time > self.interval:
            app.client.chat_update(
                channel=self.channel, ts=self.ts, text=f"{self.message}..."
            )
            self.last_send_time = now
            self.update_count += 1
            # update_count가 현재의 업데이트 간격의 10배보다 많아질 때마다 업데이트 간격을 2배로 늘림
            if self.update_count/10 > self.interval:
                self.interval = self.interval*2
            
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        app.client.chat_update(
            channel=self.channel, ts=self.ts, text=self.message
        )


# @app.event("app_mention")
def handle_mention(event, say):
    # user = event["user"]
    channel = event["channel"]
    thread_ts = event["ts"]
    message = re.sub("<@.*>", "", event["text"])
    
    # 게시글키
    # 첫번째: event["ts"]
    # 그이후: event["thread_ts"]
    id_ts = event["ts"]
    if "thread_ts" in event:
        id_ts = event["thread_ts"]
    
    # say(text=f"Hello <@{user}>!")
    # say(text=f"Hello <@{user}>!", thread_ts=thread_ts)
    
    """
    llm = ChatOpenAI(
        model_name=os.environ["OPENAI_API_MODEL"],
        temperature=os.environ["OPENAI_API_TEMPERATURE"]
    )
    response = llm.invoke(message)
    say(text=response.content, thread_ts=thread_ts)
    """
    
    result = say(text="\n\nTyping...", thread_ts=thread_ts)
    ts = result["ts"]
    
    cache_client = CacheClient(
        configuration=Configurations.Laptop.v1(),
        credential_provider=CredentialProvider.from_environment_variables_v2("MOMENTO_AUTH_TOKEN", "MOMENTO_ENDPOINT"),
        default_ttl=timedelta(hours=int(os.environ["MOMENTO_TTL"]))
    )
    """
    history = MomentoChatMessageHistory.from_client_params(
        session_id=id_ts, 
        cache_client=cache_client,
        cache_name=os.environ["MOMENTO_CACHE"], 
        ttl=timedelta(hours=int(os.environ["MOMENTO_TTL"]))
    )
    """
    history = MomentoChatMessageHistory(
        session_id=id_ts,
        cache_client=cache_client,
        cache_name=os.environ["MOMENTO_CACHE"],
        ttl=timedelta(hours=int(os.environ["MOMENTO_TTL"]))
    )
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a good assistant."),
            (MessagesPlaceholder(variable_name="chat_history")),
            ("user", "{input}")
        ]
    )
    
    callback = SlackStreamingCallbackHandler(channel=channel, ts=ts)
    llm = ChatOpenAI(
        model_name=os.environ["OPENAI_API_MODEL"],
        temperature=os.environ["OPENAI_API_TEMPERATURE"],
        streaming=True,
        callbacks=[callback]
    )
    # llm.invoke(message)
    chain = prompt | llm | StrOutputParser()
    ai_message = chain.invoke({"input": message, "chat_history": history.messages})
    history.add_user_message(message)
    history.add_ai_message(ai_message)
    
    
def just_ack(ack):
    ack()


app.event("app_mention")(ack=just_ack, lazy=[handle_mention])


# 소켓 모드 핸들러를 사용해 앱을 시작
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    
    
def handler(event, context):
    logger.info("handler called")
    header = event["headers"]
    logger.info(json.dumps(header))
    
    if "x-slack-retry-num" in header:
        logger.info("SKIP > x-slack-retry-num: %s", header["x-slack-retry-num"])
        return 200
        
    # AWS Lambda 환경의 요청 정보를 앱이 처리할 수 있도록 변환해 주는 어댑터
    slack_handler = SlackRequestHandler(app=app)
    # 응답을 그대로 AWS Lambda의 반환 값으로 반환할 수 있다.
    return slack_handler.handle(event, context)
