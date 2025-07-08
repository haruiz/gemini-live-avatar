export default class GeminiAPI {
  constructor(endpoint = null) {
    if (!endpoint) {
      throw new Error("WebSocket endpoint is required.");
    }

    this.endpoint = endpoint;
    this.ws = null;
    this.isSpeaking = false;

    // Reconnection settings
    this.shouldReconnect = true;
    this.reconnectDelay = 1000; // Initial delay (ms)
    this.maxRetries = 5;
    this.retryCount = 0;
    this.reconnectTimeout = null;

    // Event Callbacks (overridable)
    this.onReady = () => {};
    this.onError = (err) => console.error("WebSocket error:", err);
    this.onClose = () => console.warn("WebSocket connection closed.");
    this.onMessage = (event) => this._defaultMessageHandler(event);
    this.onMessageParsed = () => {};
    this.onTurnComplete = () => {};
    this.onFunctionCall = () => {};
    this.onFunctionResponse = () => {};
    this.onInterrupted = () => {};
    this.onAudioData = () => {};
    this.onTextContent = () => {};

    this.connect();
  }

  connect() {
    console.log(`🌐 Connecting to ${this.endpoint}`);
    this.ws = new WebSocket(this.endpoint);

    this.ws.onopen = () => {
      console.log("✅ WebSocket connected.");
      this.retryCount = 0;
      this.reconnectDelay = 1000;
      this.onReady();
    };

    this.ws.onerror = (err) => {
      console.error("❌ WebSocket error:", err);
      this.onError(err);
    };

    this.ws.onclose = (e) => {
      console.warn("🔌 WebSocket closed:", e.reason || e.code);
      this.onClose(e);
      if (this.shouldReconnect && this.retryCount < this.maxRetries) {
        this.retryCount++;
        this.reconnectTimeout = setTimeout(() => {
          console.log(`🔁 Attempting to reconnect... (try ${this.retryCount})`);
          this.connect();
          this.reconnectDelay *= 2; // Exponential backoff
        }, this.reconnectDelay);
      } else if (this.retryCount >= this.maxRetries) {
        console.error("🚫 Max reconnection attempts reached. Giving up.");
      }
    };

    this.ws.onmessage = this.onMessage;
  }

  _defaultMessageHandler(event) {
    try {
      const data = JSON.parse(event.data);
      this.onMessageParsed(data);
        if (data.type === 'interrupted') {
            this.isSpeaking = false;
            this.onInterrupted(data?.data);
        } else if (data.type === 'audio') {
            this.onAudioData(data?.data);
        } else if (data.type === 'text') {
            this.onTextContent(data?.data);
        } else if (data.type === 'turn_complete') {
            this.onTurnComplete();
        } else if (data.type === 'function_call') {
            this.onFunctionCall(data?.data);
        } else if (data.type === 'function_response') {
            this.onFunctionResponse(data?.data);
        } else {
            console.log('Received unknown message type:', data.type);
        }
    } catch (error) {
      console.error("❌ Parsing error:", error);
      this.onError({
        message: `Error parsing response: ${error.message}`,
        error_type: 'client_error'
      });
    }
  }

  sendMessage(message) {
    if (this.ws.readyState === WebSocket.OPEN) {
      console.log(`🚀 Sending message [${message.type}]`);
      this.ws.send(JSON.stringify(message));
    } else {
      const state = this.ws.readyState;
      const states = ["CONNECTING", "OPEN", "CLOSING", "CLOSED"];
      this.onError(`WebSocket is not open (State: ${states[state] || "UNKNOWN"})`);
    }
  }

  async ensureConnected() {
    if (this.ws.readyState === WebSocket.OPEN) return;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Timeout")), 5000);

      const handleOpen = () => {
        clearTimeout(timeout);
        cleanup();
        resolve();
      };

      const handleError = (err) => {
        clearTimeout(timeout);
        cleanup();
        reject(err);
      };

      const cleanup = () => {
        this.ws.removeEventListener("open", handleOpen);
        this.ws.removeEventListener("error", handleError);
      };

      this.ws.addEventListener("open", handleOpen);
      this.ws.addEventListener("error", handleError);
    });
  }

  disconnect() {
    this.shouldReconnect = false;
    clearTimeout(this.reconnectTimeout);
    if (this.ws) {
      console.log("🔌 Manually disconnecting...");
      this.ws.close();
    }
  }

  sendAudioChunk(base64Audio) {
    this.sendMessage({ type: "audio", data: base64Audio });
  }

  sendImage(base64Image) {
    this.sendMessage({ type: "image", data: base64Image });
  }

  sendTextMessage(text) {
    this.sendMessage({ type: "text", data: text });
  }

  sendEndMessage() {
    this.sendMessage({ type: "end" });
  }
}
