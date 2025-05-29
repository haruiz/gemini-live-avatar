export default class MediaHandler {
  constructor(videoElement) {
    this.videoElement = videoElement ?? null;
    this.currentStream = null;
    this.isWebcamActive = false;
    this.isScreenActive = false;
    this.frameCapture = null;
    this.frameCallback = null;
    this.usingFrontCamera = true;
  }

  async startWebcam(useFrontCamera = true) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: 1280,
          height: 720,
          facingMode: useFrontCamera ? "user" : "environment"
        }
      });
      this.handleNewStream(stream);
      this.isWebcamActive = true;
      this.usingFrontCamera = useFrontCamera;
      this.dispatch("stream-start", { source: "webcam" });
      return true;
    } catch (error) {
      console.error("Error accessing webcam:", error);
      return false;
    }
  }

  async startScreenShare() {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true
      });
      this.handleNewStream(stream);
      this.isScreenActive = true;

      // Stop on browser-level "Stop Sharing"
      stream.getVideoTracks()[0].addEventListener("ended", () => {
        this.stopAll();
      });

      this.dispatch("stream-start", { source: "screen" });
      return true;
    } catch (error) {
      console.error("Error sharing screen:", error);
      return false;
    }
  }

  async switchCamera() {
    if (!this.isWebcamActive) return false;
    const newFacingMode = !this.usingFrontCamera;
    await this.stopAll();
    const success = await this.startWebcam(newFacingMode);
    if (success && this.frameCallback) {
      this.startFrameCapture(this.frameCallback);
    }
    return success;
  }

  handleNewStream(stream) {
    if (this.currentStream) {
      this.stopAll();
    }
    this.currentStream = stream;
    if (this.videoElement) {
      this.videoElement.srcObject = stream;
      this.videoElement.classList.remove("hidden");
    }
  }

  stopAll() {
    if (this.currentStream) {
      this.currentStream.getTracks().forEach(track => track.stop());
      this.currentStream = null;
    }
    if (this.videoElement) {
      this.videoElement.srcObject = null;
      this.videoElement.classList.add("hidden");
    }

    if (this.isWebcamActive || this.isScreenActive) {
      this.dispatch("stream-stop");
    }

    this.isWebcamActive = false;
    this.isScreenActive = false;
    this.stopFrameCapture();
  }

  startFrameCapture(onFrame) {
    this.frameCallback = onFrame;
    const captureFrame = () => {
      if (!this.currentStream || !this.videoElement) return;

      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      canvas.width = this.videoElement.videoWidth;
      canvas.height = this.videoElement.videoHeight;

      context.drawImage(this.videoElement, 0, 0, canvas.width, canvas.height);

      // Convert to JPEG and base64 encode
      const base64Image = canvas.toDataURL("image/jpeg", 0.8).split(",")[1];
      this.frameCallback(base64Image);
    };

    this.frameCapture = setInterval(captureFrame, 1000); // 1 FPS
  }

  stopFrameCapture() {
    if (this.frameCapture) {
      clearInterval(this.frameCapture);
      this.frameCapture = null;
    }
  }

  dispatch(name, detail = {}) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }
}
