import './style.css';
import MediaHandler from '/src/media/media-handler.js';
import Avatar from '/src/avatar/index.js';
import GeminiAPI from '/src/api/gemini.js';
import AudioRecorder from '/src/audio/audio-recorder.js';
import { AudioStreamer } from '/src/audio/audio-streamer.js';


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
const transcriptBox = document.getElementById("liveTranscript");

let avatar = null;
let isUsingMic = false;
let isAvatarSpeaking = false;
let isUsingCamera = false;
let isSharingScreen = false;


const mediaHandler = new MediaHandler(videoElement);
const geminiApi = new GeminiAPI("ws://localhost:8080/api/ws/live");
const audioRecorder = new AudioRecorder();
const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
const audioStreamer = new AudioStreamer(audioContext);
let currentTurnText = "";
let currentTurn = 0;
let lastAudioTurn = -1;
let hasShownSpeakingMessage = false;

// transcription management
let currentTranscriptIndex = -1;
let transcriptWords = [];

function updateTranscriptWords(words) {
    transcriptBox.innerHTML = words.map((w, i) => `<span class="word" id="word-${i}">${w.word}</span>`).join(" ");
}

function highlightTranscriptWord(index) {
    if (index === currentTranscriptIndex) return;
    const prev = document.getElementById(`word-${currentTranscriptIndex}`);
    if (prev) prev.classList.remove("active");

    const current = document.getElementById(`word-${index}`);
    if (current) current.classList.add("active");

    currentTranscriptIndex = index;
}
// === Utils ===
function togglePulse(button, active) {
    button.classList.toggle("pulse-effect", active);
}

function logMessage(sender, message) {
    const line = document.createElement('div');
    const config = {
        user: {label: 'user@console', color: 'text-cyan-400', msgColor: 'text-green-300'},
        gemini: {label: 'gemini@core', color: 'text-purple-400', msgColor: 'text-green-300'},
        debug: {label: 'system@debug', color: 'text-yellow-400', msgColor: 'text-yellow-200'},
        error: {label: 'system@error', color: 'text-red-400', msgColor: 'text-red-300'}
    };

    const {label, color, msgColor} = config[sender] || {
        label: 'unknown', color: 'text-gray-400', msgColor: 'text-gray-300'
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

geminiApi.onReady = () => logMessage("debug", "✅ Gemini API is ready.");

geminiApi.onTextContent = (outputText) => {
    if (outputText.trim()) {
        currentTurnText += outputText;
    }
};

const receivedChunks = [];


function base64ToArrayBuffer(base64) {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

function handleBase64Chunk(base64Audio) {
  const binary = atob(base64Audio);
  const buffer = new ArrayBuffer(binary.length);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < binary.length; i++) {
    view[i] = binary.charCodeAt(i);
  }
  receivedChunks.push(new Int16Array(buffer));
}

function playAllChunks() {
  // Flatten all int16 chunks
  const totalLength = receivedChunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const int16Combined = new Int16Array(totalLength);
  let offset = 0;
  for (const chunk of receivedChunks) {
    int16Combined.set(chunk, offset);
    offset += chunk.length;
  }

  // Convert to Float32
  const float32Array = new Float32Array(int16Combined.length);
  for (let i = 0; i < int16Combined.length; i++) {
    float32Array[i] = int16Combined[i] / 32768;
  }

  const audioBuffer = audioContext.createBuffer(1, float32Array.length, audioContext.sampleRate);
  audioBuffer.copyToChannel(float32Array, 0);

  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioContext.destination);
  source.start();
  avatar.speakAudio(audioBuffer);
}

geminiApi.onTurnComplete = () => {
    logMessage("debug", "🔄 Turn complete.");
    if (currentTurnText.trim()) {
        if (avatar) {
            isAvatarSpeaking = true;
            logMessage("gemini", currentTurnText);
            avatar.speakText(currentTurnText);
        } else {
            logMessage("debug", "⚠️ Avatar not loaded, skipping speech.");
        }
    }
    geminiApi.isSpeaking = false;
    currentTurnText = "";
    lastAudioTurn = currentTurn;
    audioStreamer.complete();

    // Clear audio chunks if any
    if (receivedChunks.length > 0) {
        receivedChunks.length = 0;
    }

    // ✅ Reset live transcript
    transcriptBox.innerHTML = "";
    transcriptWords = [];
    currentTranscriptIndex = -1;
    transcriptBox.classList.add("hidden");

}

geminiApi.onAudioData = async (audioMesage) => {
    try {

      let audioData = audioMesage.audio
      let audioWords = audioMesage.words;


    if (!geminiApi.isSpeaking || lastAudioTurn !== currentTurn) {
      logMessage("debug", "🔊 Playing audio data...");
      geminiApi.isSpeaking = true;
      lastAudioTurn = currentTurn;
    }

    // Ensure audioData is base64 string
    if (typeof audioData !== "string") {
      console.error("Expected base64-encoded audio string, got:", typeof audioData);
      return;
    }
    // Decode base64 to ArrayBuffer
    const arrayBuffer = base64ToArrayBuffer(audioData);
    const int16Array = new Int16Array(arrayBuffer);
    const float32Array = new Float32Array(int16Array.length);
    //
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 32768;
    }
    //
    // play user streamer
    // const audioBuffer = audioContext.createBuffer(1, float32Array.length, audioContext.sampleRate);
    // audioBuffer.getChannelData(0).set(float32Array);
   ////audioStreamer.addPCM16(new Uint8Array(arrayBuffer));
    //audioStreamer.resume();

  // play audio using AudioContext

  // const audioBuffer = audioContext.createBuffer(1, float32Array.length, audioContext.sampleRate);
  // audioBuffer.copyToChannel(float32Array, 0);
  // const source = audioContext.createBufferSource();
  // source.buffer = audioBuffer;
  // source.connect(audioContext.destination);
  // source.start();
  // console.log("Speaking audio with words:", audioWords);

  await avatar.speakAudio(int16Array, audioWords);


  } catch (error) {
    console.error("Error playing audio:", error);
  }
};


geminiApi.onFunctionCall = (fn) => {
    logMessage("debug", `🔧 Function call: ${fn.name} with args ${JSON.stringify(fn.args)}, response: ${fn.result}`);
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


geminiApi.onMessageParsed = async (message) => {
    //logMessage("debug", `📬 Parsed message: ${JSON.stringify(data, null, 2)}`);
    if (message.type === "config") {

        //logMessage("debug", `📬 Configuration received: ${JSON.stringify(message, null, 2)}`);
        avatar = new Avatar(nodeAvatar, {
            ttsEndpoint: "https://texttospeech.googleapis.com/v1beta1/text:synthesize",
            ttsApikey: message.ttsApikey,
            lipsyncModules: ["en"],
            cameraView: "upper",
            lightAmbientIntensity: 1,
            ttsLang: message.ttsLang,
            ttsVoice: message.ttsVoice,
            avatarPath : message.avatarPath,
        });

        avatar.onTranscript = (currentWord) => {
                if (currentWord.trim()) {
                // Show transcript box
                if (transcriptBox.classList.contains("hidden")) {
                    transcriptBox.classList.remove("hidden");
                }

                // Add word to live transcript
                const wordId = `word-${transcriptWords.length}`;
                const span = document.createElement("span");
                span.className = "word";
                span.id = wordId;
                span.textContent = currentWord;
                transcriptBox.appendChild(span);

                // Scroll to bottom if needed
                transcriptBox.scrollTop = transcriptBox.scrollHeight;

                // Highlight the new word
                if (currentTranscriptIndex >= 0) {
                    const prev = document.getElementById(`word-${currentTranscriptIndex}`);
                    if (prev) prev.classList.remove("active");
                }
                span.classList.add("active");
                currentTranscriptIndex = transcriptWords.length;

                transcriptWords.push(currentWord);
            }
        }

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
    else if (message.type === "error") {
        logMessage("error", `❌ Error from Server: ${message.data?.message}`);
    }
    else if( message.type === "debug") {
        logMessage("debug", `ℹ️ Info from Server: ${message.data?.message}`);
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
