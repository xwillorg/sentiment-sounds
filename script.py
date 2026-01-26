from time import sleep
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
import threading

client = udp_client.SimpleUDPClient("127.0.0.1", 11000)

def osc_handler(address, *args):
    print(f"[OSC] {address}: {args}")

osc_dispatcher = dispatcher.Dispatcher()
osc_dispatcher.set_default_handler(osc_handler)

server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 11001), osc_dispatcher)
server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()
analyzer = SentimentIntensityAnalyzer()

class midilane:
    def __init__(self, index, name, volume, duration):
        self.index = index
        self.name = name
        self.volume = volume
        self.duration = duration
        self.active = False

    def __repr__(self):
        return f"midilane({self.name}, vol={self.volume}, dur={self.duration})"

    def fade(self, target_vol, duration, steps=15):
        self.active = target_vol > 0
        print(f"  [{self.name}] fade to {target_vol} over {duration}s")

        def do_fade():
            start_vol = self.volume
            for i in range(steps):
                vol = start_vol + (target_vol - start_vol) * (i + 1) / steps
                client.send_message("/live/track/set/volume", [self.index, vol])
                sleep(duration / steps)
            self.volume = target_vol

        threading.Thread(target=do_fade, daemon=True).start()

def main():
    print("(Sentinent sounds)")

    numberOfTracks = 9
    tracks = []
    for i in range(numberOfTracks):
        tracks.append(midilane(i, f"track{i}", 0.0, 0.0))

    middle = len(tracks) // 2       
    neutral = tracks[middle]

    print("  [neutral lane: {}]".format(neutral.name))
    print(format(tracks))

    current = middle
    tracks[middle].fade(0.85, 0.0)
    track_timers = {}

    def fade_out_track(track_index):
        nonlocal current
        if track_index != middle:
            if track_index == current:
                tracks[track_index].fade(0.0, 2.0)
                print(f"  [timeout: track{track_index}]")
                if current > middle:
                    current -= 1
                elif current < middle:
                    current += 1
                print(f"  [current reset to: {current}]")

                if current != middle and current in track_timers:
                    if not track_timers[current].is_alive():
                        fade_out_track(current)

    while True:
        try:
            text = input("You: ").strip()
            if not text:
                continue

            scores = analyzer.polarity_scores(text)
            pos = scores['pos']
            compound = scores['compound']

            print(f"  [sentiment: pos={pos:.2f}, neg={scores['neg']:.2f}, compound={compound:.2f}]")

            previous = current
            if compound > 0.05:
                current = max(current - 1, 0)
            elif compound < -0.05:
                current = min(current + 1, numberOfTracks - 1)

            print(f"  [current: {current}]")

            if current != previous and abs(current - middle) > abs(previous - middle):
                tracks[current].fade(0.85, 2.0)

            if current != middle:
                if current in track_timers and track_timers[current].is_alive():
                    track_timers[current].cancel()

                stay_duration = len(text) * 1
                print(f"  [track{current} stay: {stay_duration}s]")
                timer = threading.Timer(stay_duration, fade_out_track, args=[current])
                timer.daemon = True
                timer.start()
                track_timers[current] = timer

        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()