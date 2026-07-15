package com.example.agent;

import org.springaicommunity.agentcore.annotation.AgentCoreInvocation;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.stereotype.Service;

@SpringBootApplication
public class AgentApplication {

    public static void main(String[] args) {
        SpringApplication.run(AgentApplication.class, args);
    }

    /**
     * AgentCore Runtime에서 호스팅되는 최소 구성의 대화형 에이전트입니다.
     * /invoke 엔드포인트를 통해 사용자 메시지를 받아 LLM 응답을 반환합니다.
     */
    public record AgentRequest(String message) {}

    @Service
    public static class ConversationalAgent {

        private final ChatClient chatClient;

        ConversationalAgent(ChatModel chatModel) {
            this.chatClient = ChatClient.builder(chatModel)
                    .defaultSystem("You are a helpful assistant. Answer concisely.")
                    .build();
        }

        @AgentCoreInvocation
        public String chat(AgentRequest request) {
            return chatClient.prompt(request.message()).call().content();
        }
    }
}
