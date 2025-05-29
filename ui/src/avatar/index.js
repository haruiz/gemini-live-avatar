import { TalkingHead } from "talkinghead";

export default class Avatar {
  constructor(nodeAvatar, config = {}) {
    this.nodeAvatar = nodeAvatar;
    this.config = config;
    this.head = null;
    this.onLoading = (status, progress) => {
      console.log(`Avatar loading: ${status}`, progress ? `Progress: ${progress.percent}%` : "");
    }
  }

  async load() {
    const {
      ttsApikey,
      lipsyncModules = ["en"],
      cameraView = "upper",
      lightAmbientIntensity = 1,
      avatarPath = "https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png",
      body = "F",
      avatarMood = "neutral",
      ttsLang,
      ttsVoice,
      lipsyncLang = "en"
    } = this.config;

    this.onLoading("start");

    try {
      this.head = new TalkingHead(this.nodeAvatar, {
        ttsEndpoint: "https://texttospeech.googleapis.com/v1beta1/text:synthesize",
        ttsApikey,
        lipsyncModules,
        cameraView,
        lightAmbientIntensity,
      });

      await this.head.showAvatar(
        {
          url: avatarPath,
          body,
          avatarMood,
          ttsLang,
          ttsVoice,
          lipsyncLang,
        },
        (ev) => {
          if (ev.lengthComputable) {
            const percent = Math.min(100, Math.round((ev.loaded / ev.total) * 100));
            this.onLoading("progress", { percent });
          }
        }
      );

      this.onLoading("complete");
    } catch (err) {
      console.error("❌ Failed to load avatar:", err);
      this.onLoading("error", { error: err });
    }
  }

  /**
   * Make the avatar speak a given text.
   * @param {string} text
   */
  speak(text) {
    this.head?.speakText?.(text);
  }

  /**
   * Make the avatar play a gesture.
   * @param gesture
   * @param duration
   */
  playGesture(gesture, duration = 3) {
    if (!this.head) {
      console.error("❌ Avatar not loaded, cannot play gesture.");
      return;
    }
    this.head.playGesture(gesture, duration);
  }

  setLighting(opt){
    if (!this.head) {
      console.error("❌ Avatar not loaded, cannot set lighting.");
      return;
    }
    this.head.setLighting(opt);
  }

}
