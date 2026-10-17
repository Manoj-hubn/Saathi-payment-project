/**
 * Replaceable Speech Recognition Provider Adapter
 * Encapsulates browser SpeechRecognition with interface for pluggable external speech providers.
 */

export class BaseSpeechProvider {
  isAvailable() {
    return false;
  }
  start(onResult, onError, onEnd) {
    throw new Error('Method not implemented');
  }
  stop() {}
}

export class BrowserSpeechProvider extends BaseSpeechProvider {
  constructor() {
    super();
    this.recognition = null;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      this.recognition = new SR();
      this.recognition.lang = 'en-IN';
      this.recognition.interimResults = true;
      this.recognition.continuous = false;
    }
  }

  isAvailable() {
    return !!this.recognition;
  }

  start(onResult, onError, onEnd) {
    if (!this.recognition) {
      if (onError) onError('Speech recognition is not supported in this browser. Please type your request.');
      return;
    }

    let finalTranscript = '';

    this.recognition.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const item = e.results[i][0];
        if (e.results[i].isFinal) {
          finalTranscript += item.transcript;
        } else {
          interim += item.transcript;
        }
      }
      if (onResult) {
        onResult({
          transcript: finalTranscript || interim,
          isFinal: !!finalTranscript
        });
      }
    };

    this.recognition.onerror = (e) => {
      if (onError) onError('Microphone error: ' + (e.error || 'Speech recognition failed.'));
    };

    this.recognition.onend = () => {
      if (onEnd) onEnd(finalTranscript);
    };

    try {
      this.recognition.start();
    } catch (err) {
      if (onError) onError('Could not start microphone: ' + err.message);
    }
  }

  stop() {
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {
        // Ignored if already stopped
      }
    }
  }
}

export const speechProvider = new BrowserSpeechProvider();
