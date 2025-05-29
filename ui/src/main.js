import './style.css';
import MediaHandler from '/src/media/media-handler.js';
import Avatar from '/src/avatar/index.js';
import GeminiAPI from '/src/api/gemini.js';
import AudioRecorder from '/src/audio/audio-recorder.js';

// === DOM Elements ===
const textInput = document.getElementById('text');
const sendBtn = document.getElementById('btnSend');
const micBtn = document.getElementById('mic');
const cameraBtn = document.getElementById('camera');
const screenBtn = document.getElementById('screenShare');
const videoElement = document.getElementById('videoPreview');
const nodeAvatar = document.getElementById('avatar');
const nodeLoading = document.getElementById('loading');
const outputBox = document.getElementById('outputBox');

let avatar = null;
let isUsingMic = false;
let isAvatarSpeaking = false;
let isUsingCamera = false;
let isSharingScreen = false;

// === Utils ===
function togglePulse(button, active) {
    button.classList.toggle("pulse-effect", active);
}

function logMessage(sender, message) {
    const line = document.createElement('div');
    const config = {
        user: {label: 'user@console', color: 'text-cyan-400', msgColor: 'text-green-300'},
        gemini: {label: 'gemini@core', color: 'text-purple-400', msgColor: 'text-green-300'},
        debug: {label: '[debug]', color: 'text-yellow-400', msgColor: 'text-yellow-200'},
    };

    const {label, color, msgColor} = config[sender] || {
        label: 'system',
        color: 'text-white',
        msgColor: 'text-gray-300'
    };
    line.innerHTML = `<span class="${color}">${label}</span>: <span class="${msgColor}">${message}</span>`;
    outputBox.appendChild(line);
    outputBox.scrollTop = outputBox.scrollHeight;
}

function showPreviewAboveButton(button) {
    const rect = button.getBoundingClientRect();
    videoElement.style.position = "fixed";
    videoElement.style.left = `${rect.left + rect.width / 2 - 150}px`;
    videoElement.style.top = `${rect.top - 300}px`;
    videoElement.classList.remove("hidden");
    videoElement.classList.add("opacity-100");
}

const mediaHandler = new MediaHandler(videoElement);
const geminiApi = new GeminiAPI("ws://localhost:8080/api/ws/live");
const audioRecorder = new AudioRecorder();
const audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: 24000});
let currentTurnText = "";

geminiApi.onReady = () => logMessage("debug", "✅ Gemini API is ready.");

geminiApi.onTextContent = (outputText) => {
    if (outputText.trim()) {
        currentTurnText += outputText;
    }
};

geminiApi.onTurnComplete = () => {
    logMessage("debug", "🔄 Turn complete.");
    if (currentTurnText.trim()) {
        if (avatar) {
            isAvatarSpeaking = true;
            logMessage("gemini", currentTurnText);
            avatar.speak(currentTurnText);
        } else {
            logMessage("debug", "⚠️ Avatar not loaded, skipping speech.");
        }
    }
    currentTurnText = "";
}

geminiApi.onFunctionCall = (fn) => {
    logMessage("debug", `🔧 Function call: ${fn.name} with args ${JSON.stringify(fn.args)}`);
    // Handle function calls here if needed
    if( fn.name === "turn_on_the_lights") {
        avatar.playGesture("thumbup", 3);
        const color = fn.args?.color || 0xff0000;
        avatar.setLighting({
          lightAmbientColor: color,
          lightAmbientIntensity: 5,
          lightDirectColor: color,
          lightDirectIntensity: 20
        });
    }
    else if( fn.name === "turn_off_the_lights") {
        avatar.playGesture("thumbdown", 3);
        avatar.setLighting({
          lightAmbientColor: 0xffffff,
          lightAmbientIntensity: 2,
          lightDirectColor: 0x8888aa,
          lightDirectIntensity: 30,
          lightDirectPhi: 0.1,
          lightDirectTheta: 2,
          lightSpotColor: 0x3388ff,
          lightSpotIntensity: 0,
          lightSpotPhi: 0.1,
          lightSpotTheta: 4,
          lightSpotDispersion: 0
        });
    }
}

geminiApi.onMessageParsed = async (data) => {
    //logMessage("debug", `📬 Parsed message: ${JSON.stringify(data, null, 2)}`);

    if (data.type === "config") {
        avatar = new Avatar(nodeAvatar, {
            ttsEndpoint: "https://texttospeech.googleapis.com/v1beta1/text:synthesize",
            ttsApikey: data.ttsApikey,
            lipsyncModules: ["en"],
            cameraView: "upper",
            lightAmbientIntensity: 1,
            ttsLang: data.ttsLang,
            ttsVoice: data.ttsVoice,
            avatarPath : data.avatarPath,
        });

        avatar.onLoading = (status, progress) => {
            if (status === "start") {
                nodeLoading.textContent = "Loading...";
                nodeLoading.style.display = "block";
            } else if (status === "progress") {
                nodeLoading.textContent = `Loading ${progress.percent}%`;
            } else if (status === "complete") {
                nodeLoading.style.display = "none";
            }
        };

        try {
            await avatar.load();
        } catch (err) {
            console.error("❌ Avatar failed to load:", err);
            nodeLoading.style.display = "none";
            logMessage("debug", `❌ Avatar loading error: ${err.message}`);
        }
    }
};

window.addEventListener("stream-start", (e) => {
    logMessage("debug", `📡 Stream started: ${e.detail.source}`);
});

window.addEventListener("stream-stop", () => {
    logMessage("debug", "🛑 Stream stopped");
    videoElement.classList.add("hidden");
    videoElement.classList.remove("opacity-100");
    isUsingCamera = false;
    isSharingScreen = false;
    togglePulse(cameraBtn, false);
    togglePulse(screenBtn, false);
});

function handleSendText() {
    const text = textInput.value.trim();
    if (text) {
        geminiApi.sendTextMessage(text);
        logMessage("user", text);
        textInput.value = "";
    }
}

sendBtn.addEventListener("click", handleSendText);
textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        handleSendText();
    }
});

cameraBtn.addEventListener("click", async () => {
    const active = mediaHandler.isWebcamActive;
    if (active) {
        mediaHandler.stopAll();
        isUsingCamera = false;
    } else {
        const started = await mediaHandler.startWebcam(true);
        if (started) {
            isUsingCamera = true;
            showPreviewAboveButton(cameraBtn);
            mediaHandler.startFrameCapture((base64Image) => {
                geminiApi.sendImage(base64Image);
            });
        }
    }
    togglePulse(cameraBtn, isUsingCamera);
});

screenBtn.addEventListener("click", async () => {
    const active = mediaHandler.isScreenActive;
    if (active) {
        mediaHandler.stopAll();
        isSharingScreen = false;
    } else {
        const started = await mediaHandler.startScreenShare();
        if (started) {
            isSharingScreen = true;
            showPreviewAboveButton(screenBtn);
            mediaHandler.startFrameCapture((base64Image) => {
                geminiApi.sendImage(base64Image);
            });
        }
    }
    togglePulse(screenBtn, isSharingScreen);
});

document.addEventListener("visibilitychange", () => {
    const isVisible = document.visibilityState === "visible";
    avatar?.head?.[isVisible ? "start" : "stop"]?.();
    if (!isVisible && !isUsingMic) {
        mediaHandler.stopAll();
    }
});

let currentTurn = 0;
let hasShownSpeakingMessage = false;

async function startRecording() {
    try {
        await audioContext.resume();
        await audioRecorder.start();
        hasShownSpeakingMessage = false;
        currentTurn++;
        audioRecorder.on('data', (base64Data) => {
            if (!hasShownSpeakingMessage) {
                logMessage('debug', '🎤 Recording started, sending audio chunks...');
                hasShownSpeakingMessage = true;
            }
            geminiApi.sendAudioChunk(base64Data);
        });
        isUsingMic = true;
    } catch (error) {
        console.error('Error starting recording:', error);
        logMessage('debug', `❌ Error starting recording: ${error.message}`);
    }
}

function stopRecording() {
    audioRecorder.stop();
    isUsingMic = false;
    hasShownSpeakingMessage = false;
    logMessage('debug', '🎤 Recording stopped, audio sent to Gemini API.');
    geminiApi.sendEndMessage();
}

micBtn.addEventListener("click", async () => {
    if (isUsingMic) {
        stopRecording();
    } else {
        await startRecording();
    }
    togglePulse(micBtn, isUsingMic);
});
