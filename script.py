from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pythonosc import udp_client, dispatcher, osc_server
import threading
import time

param_indices = {}  # Will store parameter name -> index mapping

def osc_handler(address, *args):
    """Handle incoming OSC messages from Ableton"""
    if address == "/live/device/get/parameters/name":
        # Parse parameter names and build index lookup
        # args = (track, device, name0, name1, name2, ...)
        names = args[2:]  # Skip track and device IDs
        for i, name in enumerate(names):
            param_indices[name] = i
        print(f"  [OSC] Loaded {len(names)} parameters")
    else:
        print(f"  [OSC] {address}: {args}")

def start_osc_listener():
    """Start OSC listener for Ableton responses on port 11001"""
    d = dispatcher.Dispatcher()
    d.set_default_handler(osc_handler)
    server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 11001), d)
    server.serve_forever()

def main():
    # Start listener thread for Ableton responses
    listener = threading.Thread(target=start_osc_listener, daemon=True)
    listener.start()
    print("OSC listener started on port 11001")

    analyzer = SentimentIntensityAnalyzer()
    client = udp_client.SimpleUDPClient("127.0.0.1", 11000)

    track = 0   
    device = 0  

    print("Querying device parameters...")
    client.send_message("/live/device/get/parameters/name", [track, device])
    time.sleep(1.0)

    print("\nParameter indices loaded:")
    for name in ['Filter On', 'Filter Freq', 'Filter Res', 'LFO On', 'LFO Rate', 'Volume', 'Tone', 'Osc-A Level']:
        if name in param_indices:
            print(f"  {name}: {param_indices[name]}")

    print("\nEnabling Filter and LFO...")
    if 'Filter On' in param_indices:
        client.send_message("/live/device/set/parameter/value", [track, device, param_indices['Filter On'], 1.0])
        print(f"  Filter On (idx {param_indices['Filter On']})")
    if 'LFO On' in param_indices:
        client.send_message("/live/device/set/parameter/value", [track, device, param_indices['LFO On'], 1.0])
        print(f"  LFO On (idx {param_indices['LFO On']})")

    print("=" * 50)
    print("Sentiment Analyzer")
    print("=" * 50)
    print("Type text to analyze sentiment")
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
                    mood = "😊 POSITIVE"
                elif compound <= -0.05:
                    mood = "😞 NEGATIVE"
                else:
                    mood = "😐 NEUTRAL"
                
                print(f"  → {mood}\n")

                compound_norm = scores['compound'] * 0.5 + 0.5  
                param_mapping = [
                    ('Filter Freq', compound_norm),
                    ('Filter Res', scores['neg']),
                    ('Volume', 0.5 + scores['pos'] * 0.3),
                    ('LFO Rate', scores['neu'] * 0.5),
                ]

                for param_name, value in param_mapping:
                    if param_name in param_indices:
                        idx = param_indices[param_name]
                        client.send_message("/live/device/set/parameter/value", [track, device, idx, value])
                        print(f"Sent {param_name} (idx {idx}): {value:.3f}")
                    else:
                        print(f"Warning: {param_name} not found")

                
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()