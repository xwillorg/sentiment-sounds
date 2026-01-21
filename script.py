from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
import threading
import random
import time

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

def fade_track(track, target_vol, duration, steps=30):
    """Gradually fade a track's volume"""
    # Get approximate current volume (we'll estimate based on our last setting)
    for i in range(steps):
        vol = target_vol * (i + 1) / steps
        client.send_message("/live/track/set/volume", [track, vol])
        time.sleep(duration / steps)

def main():
    print("Type text to control Drift vinyl distortion based on sentiment")
    print("Commands: 'list' to show parameters, 'devices' to show devices")
    print("Press Ctrl+C to quit\n")

    # Settings: track 1 = index 0, Drift device index, vinyl distortion param
    track = 0
    device = 2  # Change this if Drift is not the first device
    param = 0   # We'll find the right index with 'list'

    value = 0.0

    while True:
        try:
            text = input("> ").strip()
            if not text:
                continue

            if text == "devices":
                client.send_message("/live/track/get/devices", [track])
                print(f"  Requesting devices on track {track}...")
                import time
                time.sleep(0.5)
                continue

            if text == "list":
                client.send_message("/live/device/get/parameters/name", [track, device])
                print(f"  Requesting parameter names for track {track}, device {device}...")
                import time
                time.sleep(0.5)
                continue

            scores = analyzer.polarity_scores(text)

            # Use positive score (0 to 1) for parameter value
            pos = scores['pos']
            compound = scores['compound']

            print(f"  pos: {pos:.2f}, neg: {scores['neg']:.2f}, neu: {scores['neu']:.2f}, compound: {compound:.2f}")

            # Adjust value based on compound sentiment
            if compound > 0.05:
                value += 1
            elif compound < -0.05:
                value -= 1
            else:
                # Compound between -0.5 and 0.5: move value toward 0
                if value > 0:
                    value -= 1
                elif value < 0:
                    value += 1

            print(f"  -> Compound: {compound:.2f}, Value: {value}")
            #client.send_message("/live/device/set/parameter/value", [track, device, param, value])
            #print(f"  Setting track {track}, device {device}, param {param} to {value}")
            if value == 1:
                print("Setting volume to 1")
                fade_track(1, 1.0, 4.0)
            elif value == 2:
                fade_track(2, 1.0, 4.0)
            elif value == 0:
                print("Setting volume to 0")
                fade_track(1, 0.0, 2.0)
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()