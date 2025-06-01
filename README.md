# Gemini Live Avatar

**Gemini Live Avatar** is an **open-source web application** that aims to provide a conversational, real-time interface using voice, text, and animated avatars in the browser. While the user interface runs entirely in the browser, it depends on a backend server to handle WebSocket communication and interact with the **[Gemini Live API](https://ai.google.dev/gemini-api/docs/live)**. Under the hood, the Gemini Live API enables seamless, low-latency interactions—allowing the 3D avatar to listen, speak, and react in real time, making conversations with AI feel more natural and engaging.

## ✨ Features

- ⚡ **Real-time interaction** powered by the Gemini Live API
- 🎤 **Speech-to-Text** User can interact with the avatar using voice input
- 🗣️ **Text-to-Speech** for the avatar's spoken responses, including lipsync and facial animations
- 💬 **Text prompting** with Gemini’s streaming multimodal responses
- 🧠 **Avatar animation** using [Ready Player Me](https://readyplayer.me/) and [Talking Head](https://github.com/met4citizen/TalkingHead)
- 🎥 **Webcam and screen sharing** capabilities for real-time context
- 📄 **Multimodal chat log** displaying user prompts and Gemini responses

### 🧠 How It Works

Gemini Live Avatar provides an interactive loop where the avatar listens, sees, responds, and reasons in real time:

1. **User speaks, types, or shares screen/camera input**.
2. The server receives, processes, and analyzes input streams using the **Gemini Live API**, which handles the request with full multimodal context—including what the avatar "sees" through shared screen or camera input.
3. **The avatar responds instantly** as Gemini-generated responses are received by the frontend and drive the avatar’s animation:
   * **Text responses** are displayed in the chat log in real time.
   * **Speech responses** are synthesized and played back, with the avatar lip-syncing and animating to match the spoken content.
4. **Function calling** is triggered dynamically when needed:
   * 🔍 **Google Search grounding** enhances answers with fresh external information.
   * ⚙️ Some **Custom tools** has been implemented, such as ` Turn the green(any color) lights on`, `turn off light`, to demonstrate how function calling can be integrated into the system.
5. **Screen and camera content** can be referenced directly in user queries like:

   * *"What’s in this slide?"*
   * *"Can you summarize the text on screen?"*
   * *"Tell me what’s in front of the camera."*

This real-time loop enables expressive, grounded, and multimodal conversations with an avatar interface.

### Roadmap

- [x] End-to-end Gemini Live API integration
- [x] Speech-to-Text & Text-to-Speech functionality
- [x] Text input with streaming responses including multimodal content
- [x] Webcam and screen sharing for real-time context
- [x] Avatar animation with Ready Player Me
- [ ] Avatar animation with Mixamo
- [x] Function calling by providing the MCP server URL
- [ ] Integrate Gemini native audio output support
- [ ] Integrate with ADK
- [ ] Add interruption support for real-time responses

### Prerequisites

- [Node.js](https://nodejs.org/) v18 or later
- A [Google AI Studio](https://ai.google.dev/) project with a Gemini API key
- Python 3.11+
- (Optional) Ready Player Me avatar URL

### Installation

# Development Setup

```bash
git clone https://github.com/haruiz/gemini-live-avatar.git
cd gemini-live-avatar
uv sync
````

# PIP installation

```bash
pip install gemini-live-avatar
```

### Run the App

```bash
gemini-live-avatar --google-search-grounding --workers 1 --avatar-path https://models.readyplayer.me/<AvatarID>.glb
```
Then open your browser at: [http://localhost:8080](http://localhost:8080)


## 🧠 Using Ready Player Me

This project integrates avatars from [Ready Player Me](https://readyplayer.me/), which offers fully rigged, customizable 3D characters ideal for expressive visual representation. Facial movements—including lip sync, eye tracking, and gestures—are animated in real time using the open-source [Talking Head](https://github.com/met4citizen/TalkingHead) library by [Mika Suominen](https://github.com/met4citizen), and are driven by responses from the Gemini Live API. Users can personalize the experience by supplying their own Ready Player Me avatar URL.

## 📦 Built With

* [Gemini Live API](https://ai.google.dev/gemini-api/docs/live)
* [Vite](https://vitejs.dev/) – Modern dev environment
* [Ready Player Me](https://readyplayer.me/) – Avatar creation platform
* [Three.js](https://threejs.org/) – 3D rendering engine

## 🤝 Contributing

Contributions, suggestions, and pull requests are very welcome!
If you'd like to contribute, please open an issue or submit a PR.


