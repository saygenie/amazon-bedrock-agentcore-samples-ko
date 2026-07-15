import { PipecatClient } from "@pipecat-ai/client-js";
import {
  WebSocketTransport,
  ProtobufFrameSerializer,
} from "@pipecat-ai/websocket-transport";

const logEl = document.getElementById("log");
const statusEl = document.getElementById("statusText");
const btnConnect = document.getElementById("btnConnect");
const btnDisconnect = document.getElementById("btnDisconnect");
const serverUrlInput = document.getElementById("serverUrl");

let pcClient = null;
// 끼어들기 시 _mediaManager.userStartedSpeaking()을 호출할 수 있도록
// 원본 transport 참조를 유지합니다.
let transport = null;

function log(msg, cls) {
  const div = document.createElement("div");
  div.textContent = `${new Date().toISOString().slice(11, 23)} ${msg}`;
  if (cls) div.className = cls;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
  console.log(msg);
}

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = cls || "";
}

function setButtons(connected) {
  btnConnect.disabled = connected;
  btnDisconnect.disabled = !connected;
}

async function connect() {
  const serverUrl = serverUrlInput.value.trim();
  if (!serverUrl) {
    log("Please enter a server URL", "log-error");
    return;
  }

  setStatus("Connecting...", "connecting");
  setButtons(true);
  log("Connecting via " + serverUrl + "...", "log-system");

  try {
    transport = new WebSocketTransport({
      serializer: new ProtobufFrameSerializer(),
      recorderSampleRate: 16000,
      playerSampleRate: 24000,
    });

    pcClient = new PipecatClient({
      transport: transport,
      enableMic: true,
      enableCam: false,
      callbacks: {
        onConnected: () => {
          setStatus("Connected", "connected");
          log("Connected", "log-system");
        },
        onDisconnected: () => {
          setStatus("Disconnected", "disconnected");
          setButtons(false);
          log("Disconnected", "log-system");
        },
        onBotReady: (data) => {
          log("Bot ready", "log-system");
        },
        onBotStartedSpeaking: () => {
          log("Bot speaking...", "log-system");
        },
        onBotStoppedSpeaking: () => {
          log("Bot stopped speaking", "log-system");
        },
        onUserStartedSpeaking: () => {
          log("User speaking...", "log-system");
          // 끼어들기를 위해 봇 오디오 재생을 중단합니다.
          // transport가 자동으로 연결하지 않으므로 내부 media manager의
          // userStartedSpeaking()을 호출합니다.
          if (transport._mediaManager) {
            transport._mediaManager.userStartedSpeaking();
          }
        },
        onUserStoppedSpeaking: () => {
          log("User stopped speaking", "log-system");
        },
        onUserTranscript: (data) => {
          if (data.final) {
            log("User: " + data.text, "log-user");
          }
        },
        onBotTranscript: (data) => {
          log("Bot: " + data.text, "log-bot");
        },
        onMessageError: (error) => {
          log("Error: " + JSON.stringify(error), "log-error");
        },
        onError: (error) => {
          log("Error: " + JSON.stringify(error), "log-error");
        },
      },
    });

    window.pcClient = pcClient;

    await pcClient.initDevices();
    log("Devices initialized", "log-system");

    // WebSocket URL을 가져오기 위해 /start 엔드포인트를 직접 요청한 후
    // 바로 연결합니다. startBotAndConnect()을 사용하면 SDK가 내부에서
    // 응답 본문을 두 번 읽어 "body stream already read" 오류가 발생합니다.
    const resp = await fetch(serverUrl, { method: "POST" });
    const data = await resp.json();
    if (!data.ws_url) {
      throw new Error("Server did not return ws_url");
    }
    log("WebSocket URL: " + data.ws_url, "log-system");

    await pcClient.connect({ wsUrl: data.ws_url });
    log("Connection complete", "log-system");
  } catch (error) {
    log("Connection error: " + error.message, "log-error");
    setStatus("Error", "disconnected");
    setButtons(false);
    if (pcClient) {
      try { await pcClient.disconnect(); } catch (e) {}
      pcClient = null;
    }
  }
}

async function disconnect() {
  if (pcClient) {
    try { await pcClient.disconnect(); } catch (e) {}
    pcClient = null;
  }
  transport = null;
  setStatus("Disconnected", "disconnected");
  setButtons(false);
}

btnConnect.addEventListener("click", connect);
btnDisconnect.addEventListener("click", disconnect);
