from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import sounddevice as sd
import numpy as np
import threading
import random
import time

SAMPLE_RATE = 44100

class AmbientLayer:
    """A single ambient sound layer that fades in/out"""
    def __init__(self, freq, duration, volume, pan=0.0, wave_type='sine'):
        self.freq = freq
        self.duration = duration
        self.volume = volume
        self.pan = pan  # -1 to 1
        self.wave_type = wave_type
        self.start_time = time.time()
        self.fade_in = min(1.0, duration * 0.3)
        self.fade_out = min(1.0, duration * 0.3)

    def is_alive(self):
        return time.time() - self.start_time < self.duration

    def get_envelope(self, t):
        """Get amplitude envelope at time t"""
        elapsed = time.time() - self.start_time
        if elapsed < self.fade_in:
            return elapsed / self.fade_in
        elif elapsed > self.duration - self.fade_out:
            return (self.duration - elapsed) / self.fade_out
        return 1.0

class Soundscape:
    """Manages layered ambient sounds"""
    def __init__(self):
        self.layers = []
        self.lock = threading.Lock()
        self.phase = {}  # Track phase for each layer
        self.running = True

    def add_layer(self, layer):
        with self.lock:
            self.layers.append(layer)
            self.phase[id(layer)] = 0.0
            print(f"    + Layer: {layer.freq:.1f}Hz, {layer.duration:.1f}s, vol:{layer.volume:.2f}")

    def audio_callback(self, outdata, frames, time_info, status):
        """Called by sounddevice to fill audio buffer"""
        t = np.arange(frames) / SAMPLE_RATE
        output = np.zeros((frames, 2))

        with self.lock:
            # Remove dead layers
            self.layers = [l for l in self.layers if l.is_alive()]

            for layer in self.layers:
                # Get phase for this layer
                phase = self.phase.get(id(layer), 0.0)

                # Generate waveform
                if layer.wave_type == 'sine':
                    wave = np.sin(2 * np.pi * layer.freq * t + phase)
                elif layer.wave_type == 'triangle':
                    wave = 2 * np.abs(2 * ((layer.freq * t + phase/(2*np.pi)) % 1) - 1) - 1
                else:  # pad-like (multiple detuned sines)
                    wave = (np.sin(2 * np.pi * layer.freq * t + phase) +
                            0.5 * np.sin(2 * np.pi * layer.freq * 1.005 * t + phase) +
                            0.5 * np.sin(2 * np.pi * layer.freq * 0.995 * t + phase)) / 2

                # Apply envelope and volume
                env = layer.get_envelope(t[0])
                wave *= env * layer.volume

                # Apply panning
                left = wave * (1 - max(0, layer.pan)) * 0.7
                right = wave * (1 + min(0, layer.pan)) * 0.7

                output[:, 0] += left
                output[:, 1] += right

                # Update phase
                self.phase[id(layer)] = phase + 2 * np.pi * layer.freq * frames / SAMPLE_RATE

        # Soft clip to prevent distortion
        output = np.tanh(output)
        outdata[:] = output.astype(np.float32)

    def start(self):
        self.stream = sd.OutputStream(
            channels=2,
            samplerate=SAMPLE_RATE,
            callback=self.audio_callback,
            blocksize=1024
        )
        self.stream.start()

    def stop(self):
        self.running = False
        self.stream.stop()
        self.stream.close()


def sentiment_to_sounds(scores, soundscape):
    """Convert sentiment scores to ambient sound layers"""
    compound = scores['compound']
    pos = scores['pos']
    neg = scores['neg']
    neu = scores['neu']

    # Base frequency: positive = higher, negative = lower
    base_freq = 220 * (2 ** (compound * 0.5))  # A3 ± half octave

    # Duration: more neutral = longer, more extreme = shorter
    duration = 3 + neu * 5 + random.uniform(-0.5, 0.5)

    # Number of layers based on intensity
    intensity = pos + neg
    num_layers = max(1, int(2 + intensity * 3))

    print(f"\n  Creating {num_layers} layers...")

    for i in range(num_layers):
        # Randomize each layer
        freq_mult = random.choice([0.5, 1, 1.5, 2, 2.5, 3])  # Harmonic series
        freq = base_freq * freq_mult + random.uniform(-5, 5)

        # Volume based on sentiment type
        if pos > neg:
            volume = 0.15 + pos * 0.2
            wave_type = random.choice(['sine', 'pad'])
        else:
            volume = 0.1 + neg * 0.15
            wave_type = random.choice(['triangle', 'pad'])

        volume *= random.uniform(0.7, 1.0)

        # Random panning
        pan = random.uniform(-0.7, 0.7)

        # Slightly different durations for movement
        layer_duration = duration * random.uniform(0.8, 1.2)

        layer = AmbientLayer(freq, layer_duration, volume, pan, wave_type)
        soundscape.add_layer(layer)


def main():
    analyzer = SentimentIntensityAnalyzer()
    soundscape = Soundscape()
    soundscape.start()

    print("=" * 50)
    print("Sentiment Soundscape")
    print("=" * 50)
    print("Type text to create layered ambient sounds")
    print("Each input adds new layers to the soundscape")
    print("Press Ctrl+C to quit\n")

    while True:
        try:
            text = input("> ")

            if text.strip():
                scores = analyzer.polarity_scores(text)

                print(f"\n  Positive:  {scores['pos']:.3f}")
                print(f"  Negative:  {scores['neg']:.3f}")
                print(f"  Neutral:   {scores['neu']:.3f}")
                print(f"  Compound:  {scores['compound']:.3f}")

                compound = scores['compound']
                if compound >= 0.05:
                    mood = "POSITIVE"
                elif compound <= -0.05:
                    mood = "NEGATIVE"
                else:
                    mood = "NEUTRAL"

                print(f"  → {mood}")

                sentiment_to_sounds(scores, soundscape)
                print()

        except KeyboardInterrupt:
            print("\n\nFading out...")
            soundscape.stop()
            print("Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()