from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pythonosc import udp_client, dispatcher, osc_server
import threading
import random
import time

client = udp_client.SimpleUDPClient("127.0.0.1", 11000)

NUM_TRACKS = 4  # Number of layering tracks

# Track which tracks are currently playing
active_tracks = {}  # track_id -> end_time

def osc_handler(address, *args):
    """Log OSC responses"""
    if "error" in address.lower():
        print(f"  [ERROR] {args}")

def start_listener():
    d = dispatcher.Dispatcher()
    d.set_default_handler(osc_handler)
    server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 11001), d)
    server.serve_forever()

def get_available_track():
    """Find a track that's not currently playing"""
    now = time.time()
    for track in range(NUM_TRACKS):
        if track not in active_tracks or active_tracks[track] < now:
            return track
    # All busy, return random
    return random.randint(0, NUM_TRACKS - 1)

def fade_track(track, target_vol, duration, steps=30):
    """Gradually fade a track's volume"""
    # Get approximate current volume (we'll estimate based on our last setting)
    for i in range(steps):
        vol = target_vol * (i + 1) / steps
        client.send_message("/live/track/set/volume", [track, vol])
        time.sleep(duration / steps)

def play_layer(track, duration, volume, filter_freq, pitch_offset):
    """Play a sound layer with fade in/out"""
    fade_time = min(2.0, duration * 0.25)
    sustain_time = duration - (fade_time * 2)

    # Set initial state
    client.send_message("/live/track/set/volume", [track, 0.0])

    # Set filter (try Operator's filter freq index)
    client.send_message("/live/device/set/parameter/value", [track, 0, 172, filter_freq])

    # Transpose the track's clip for variation
    # Actually, let's set oscillator pitch instead
    client.send_message("/live/device/set/parameter/value", [track, 0, 2, 0.5 + pitch_offset])

    # Fire the clip
    client.send_message("/live/clip_slot/fire", [track, 0])
    time.sleep(0.1)

    # Fade in
    print(f"    Track {track}: fading in...")
    for i in range(20):
        vol = volume * (i + 1) / 20
        client.send_message("/live/track/set/volume", [track, vol])
        time.sleep(fade_time / 20)

    # Sustain
    time.sleep(sustain_time)

    # Fade out
    print(f"    Track {track}: fading out...")
    for i in range(20):
        vol = volume * (20 - i - 1) / 20
        client.send_message("/live/track/set/volume", [track, vol])
        time.sleep(fade_time / 20)

    # Stop clip
    client.send_message("/live/track/set/volume", [track, 0.0])
    client.send_message("/live/clip/stop", [track, 0])

    # Mark track as free
    if track in active_tracks:
        del active_tracks[track]

def add_layer(scores):
    """Add a new sound layer based on sentiment"""
    compound = scores['compound']
    pos = scores['pos']
    neg = scores['neg']
    neu = scores['neu']

    # Find available track
    track = get_available_track()

    # Calculate layer parameters
    duration = 5 + neu * 8 + random.uniform(-1, 2)  # 4-15 seconds
    volume = 0.4 + (pos + neg) * 0.25  # Intensity = louder
    volume = min(0.75, volume * random.uniform(0.8, 1.0))

    # Filter: positive = brighter
    filter_freq = 0.3 + (compound + 1) * 0.25 + random.uniform(-0.05, 0.05)
    filter_freq = max(0.1, min(0.85, filter_freq))

    # Pitch variation
    pitch_offset = random.uniform(-0.05, 0.05)

    # Mark track as busy
    active_tracks[track] = time.time() + duration

    print(f"  + Layer on track {track}: {duration:.1f}s, vol:{volume:.2f}, filter:{filter_freq:.2f}")

    # Start in background thread
    thread = threading.Thread(
        target=play_layer,
        args=(track, duration, volume, filter_freq, pitch_offset),
        daemon=True
    )
    thread.start()

def setup_ableton():
    """Create tracks and clips for layering"""
    print("\nSetting up Ableton for layering...")

    for track in range(NUM_TRACKS):
        print(f"  Setting up track {track}...")

        # Create track if needed (this might create extras, that's ok)
        if track > 0:
            client.send_message("/live/song/create_midi_track", [-1])
            time.sleep(0.3)

        # Create clip
        client.send_message("/live/clip_slot/create_clip", [track, 0, 8.0])
        time.sleep(0.2)

        # Add notes (chord)
        client.send_message("/live/clip/add/notes", [track, 0, 48, 0.0, 8.0, 100, 0])  # C2
        client.send_message("/live/clip/add/notes", [track, 0, 60, 0.0, 8.0, 80, 0])   # C3
        client.send_message("/live/clip/add/notes", [track, 0, 67, 0.0, 8.0, 60, 0])   # G3
        time.sleep(0.1)

        # Loop it
        client.send_message("/live/clip/set/looping", [track, 0, 1])

        # Set volume to 0
        client.send_message("/live/track/set/volume", [track, 0.0])

    print("\n  Setup complete!")
    print(f"  Add a synth (Operator) to each of the {NUM_TRACKS} tracks")
    print("  Enable Filter in each Operator for best results")
    print("\n  Then just type text - sounds will layer automatically!\n")

def main():
    # Start OSC listener
    listener = threading.Thread(target=start_listener, daemon=True)
    listener.start()
    time.sleep(0.2)

    analyzer = SentimentIntensityAnalyzer()

    print("=" * 50)
    print("Sentiment Soundscape")
    print("=" * 50)
    print("\nCommands:")
    print("  'setup' - Create tracks and clips")
    print("  Or type any text to add a sound layer")
    print("\nPress Ctrl+C to quit\n")

    while True:
        try:
            text = input("> ").strip()

            if not text:
                continue

            if text.lower() == 'setup':
                setup_ableton()
                continue

            # Analyze sentiment
            scores = analyzer.polarity_scores(text)

            print(f"\n  Pos:{scores['pos']:.2f} Neg:{scores['neg']:.2f} Compound:{scores['compound']:.2f}")

            compound = scores['compound']
            mood = "POSITIVE" if compound >= 0.05 else "NEGATIVE" if compound <= -0.05 else "NEUTRAL"
            print(f"  -> {mood}")

            # Add a new layer
            add_layer(scores)
            print()

        except KeyboardInterrupt:
            print("\n\nStopping all tracks...")
            for track in range(NUM_TRACKS):
                client.send_message("/live/track/set/volume", [track, 0.0])
                client.send_message("/live/clip/stop", [track, 0])
            print("Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()
