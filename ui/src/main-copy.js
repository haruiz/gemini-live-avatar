import './style.css';
import { TalkingHead } from "talkinghead";

let head;
let isRecording = false;

const textInput = document.getElementById('text');
const sendBtn = document.getElementById('btnSend');
const micBtn = document.getElementById('mic');
const pulse = micBtn.querySelector('.mic-pulse');
const nodeAvatar = document.getElementById('avatar');
const nodeLoading = document.getElementById('loading');

// WebSocket setup
const socket = new WebSocket("ws://localhost:8080/api/ws");

socket.addEventListener("open", () => {
    console.log("✅ WebSocket connected.");
});

socket.addEventListener("error", (err) => {
    console.error("❌ WebSocket error:", err);
});

socket.addEventListener("message", async (event) => {
    let data;

    try {
        data = JSON.parse(event.data);
    } catch (err) {
        console.warn("⚠️ Ignored non-JSON message:", event.data);
        return;
    }

    switch (data.type) {
        case "config":
            console.log("⚙️ Received avatar config");

            head = new TalkingHead(nodeAvatar, {
                ttsEndpoint: "https://texttospeech.googleapis.com/v1beta1/text:synthesize",
                ttsApikey: data.ttsApikey,
                lipsyncModules: ["en"],
                cameraView: "upper",
                lightAmbientIntensity: 1,
            });

            nodeLoading.textContent = "Loading...";
            await head.showAvatar({
                url: 'https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png',
                body: 'F',
                avatarMood: 'neutral',
                ttsLang: data.ttsLang,
                ttsVoice: data.ttsVoice,
                lipsyncLang: 'en',
            }, (ev) => {
                if (ev.lengthComputable) {
                    nodeLoading.textContent = `Loading ${Math.min(100, Math.round(ev.loaded / ev.total * 100))}%`;
                }
            });

            nodeLoading.style.display = 'none';
            break;
        case "response":
            console.log("🤖 Gemini says:", data.text);
            head?.speakText(data.text);
            break;

        default:
            console.warn("⚠️ Unknown message type:", data.type);
    }
});


// Send message helper
function sendMessage() {
    const text = textInput.value.trim();
    if (text && socket.readyState === WebSocket.OPEN) {
        socket.send(text);
        textInput.value = "";
    }
}

sendBtn.addEventListener('click', sendMessage);
textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        sendMessage();
    }
});

micBtn.addEventListener('click', () => {
    isRecording = !isRecording;
    pulse.classList.toggle('hidden', !isRecording);
    console.log(isRecording ? '🎤 Recording started...' : '🛑 Recording stopped.');
});

document.addEventListener("visibilitychange", () => {
    document.visibilityState === "visible" ? head?.start() : head?.stop();
});
