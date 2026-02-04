from time import time
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
import threading
import tkinter as tk

LOG_FILE = "input_log.txt"

client = udp_client.SimpleUDPClient("127.0.0.1", 11000)

osc_dispatcher = dispatcher.Dispatcher()
server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 11001), osc_dispatcher)
server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()

analyzer = SentimentIntensityAnalyzer()


class MidiLane:
    def __init__(self, index):
        self.index = index
        self.volume = 0.0
        self.target_volume = 0.0
        self.last_sent = -1.0
        self.last_send_time = 0.0
        self.fade_speed = 1.5

    def set_target(self, vol):
        self.target_volume = max(0.0, min(1.0, vol))

    def update(self, dt, current_time):
        diff = self.target_volume - self.volume
        if abs(diff) < 0.01:
            self.volume = self.target_volume
        else:
            self.volume += diff * self.fade_speed * dt

        time_since_send = current_time - self.last_send_time
        reached_target = abs(self.volume - self.target_volume) < 0.01
        volume_changed = abs(self.volume - self.last_sent) > 0.01

        if volume_changed and (reached_target or time_since_send > 0.2):
            client.send_message("/live/track/set/volume", [self.index, self.volume])
            self.last_sent = self.volume
            self.last_send_time = current_time


class SentimentEngine:
    def __init__(self, num_tracks=9):
        self.num_tracks = num_tracks
        self.tracks = [MidiLane(i) for i in range(num_tracks)]
        self.middle = num_tracks // 2

        self.position = float(self.middle)
        self.velocity = 0.0
        self.last_update = time()
        self.last_input_time = time()

        self.friction = 0.15
        self.gravity = 0.08
        self.crash_threshold = 2.0

        self.messages = []
        self.crashed = False

        self.tracks[self.middle].volume = 0.85
        self.tracks[self.middle].target_volume = 0.85
        client.send_message("/live/track/set/volume", [self.middle, 0.85])

    def apply_sentiment(self, text):
        scores = analyzer.polarity_scores(text)
        compound = scores['compound']

        opposite_force = (self.velocity < -self.crash_threshold and compound < -0.3) or \
                        (self.velocity > self.crash_threshold and compound > 0.3)

        if opposite_force:
            self.crashed = True
            self.velocity = -self.velocity * 1.5
        else:
            force = -compound * 2.0
            if (self.velocity < 0 and compound > 0) or (self.velocity > 0 and compound < 0):
                force *= 1.0 + min(abs(self.velocity), 3.0) * 0.3
            self.velocity += force

        self.last_input_time = time()
        self.messages.append(text)
        if len(self.messages) > 20:
            self.messages.pop(0)

    def update(self):
        now = time()
        dt = now - self.last_update
        self.last_update = now

        idle_time = now - self.last_input_time

        friction_factor = self.friction * (1.0 + idle_time * 0.5)
        self.velocity *= (1.0 - friction_factor * dt)

        if idle_time > 2.0:
            distance_from_center = self.position - self.middle
            gravity_force = -distance_from_center * self.gravity * (idle_time - 2.0) * 0.5
            self.velocity += gravity_force * dt

        self.position += self.velocity * dt
        self.position = max(0.0, min(float(self.num_tracks - 1), self.position))

        if abs(self.velocity) < 0.01:
            self.velocity = 0.0

        self.update_tracks(dt, now)

        if self.crashed:
            self.crashed = False

    def update_tracks(self, dt, current_time):
        for i, track in enumerate(self.tracks):
            if self.position <= self.middle:
                if i >= self.position and i <= self.middle:
                    vol = 0.85
                else:
                    vol = 0.0
            else:
                if i >= self.middle and i <= self.position:
                    vol = 0.85
                else:
                    vol = 0.0
            track.set_target(vol)
            track.update(dt, current_time)


class SentimentApp:
    def __init__(self):
        self.engine = SentimentEngine()

        self.root = tk.Tk()
        self.root.title("sentiment sounds")
        self.root.configure(bg="white")
        self.root.geometry("600x500")

        # main container - full height, horizontal padding only
        self.main_frame = tk.Frame(self.root, bg="white")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=60, pady=(0, 260))

        # input at the very bottom (pack first so it's lowest)
        self.input_frame = tk.Frame(self.main_frame, bg="white")
        self.input_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # chat history - fills remaining space, content anchored at bottom
        self.chat_canvas = tk.Canvas(
            self.main_frame,
            bg="white",
            highlightthickness=0,
            borderwidth=0
        )
        self.chat_canvas.pack(fill=tk.BOTH, expand=True)

        self.chat_inner = tk.Frame(self.chat_canvas, bg="white")
        self.chat_window = self.chat_canvas.create_window(
            0, 0,
            window=self.chat_inner,
            anchor="s"
        )

        self.chat_canvas.bind("<Configure>", self._on_canvas_resize)
        self.message_labels = []

        self.input_entry = tk.Entry(
            self.input_frame,
            font=("Helvetica Neue", 60),
            bg="white",
            fg="#333333",
            insertbackground="#333333",
            insertwidth=2,
            borderwidth=0,
            highlightthickness=0,
            justify="center"
        )
        self.input_entry.pack(fill=tk.X)

        self.input_entry.bind("<Return>", self.on_submit)
        self.input_entry.focus_set()

        # start update loop
        self.update_loop()

    def _on_canvas_resize(self, event):
        # reposition the inner frame to stay centered
        self.chat_canvas.coords(self.chat_window, event.width // 2, event.height // 2)

    def update_chat(self):
        # clear old labels
        for label in self.message_labels:
            label.destroy()
        self.message_labels = []

        # create new labels for each message (oldest first, so newest is at bottom)
        messages = self.engine.messages[-15:]
        num_messages = len(messages)
        for i, msg in enumerate(messages):
            # newest (last) message is size 60, each older one shrinks
            position_from_bottom = num_messages - 1 - i
            font_size = max(11, 60 - position_from_bottom * 4)
            label = tk.Label(
                self.chat_inner,
                text=msg,
                font=("Helvetica Neue", font_size),
                bg="white",
                fg="#999999",
                wraplength=500,
                justify="center"
            )
            label.pack(pady=(0, 8))
            self.message_labels.append(label)

        # update canvas to reposition
        self.chat_inner.update_idletasks()
        canvas_height = self.chat_canvas.winfo_height()
        canvas_width = self.chat_canvas.winfo_width()
        self.chat_canvas.coords(self.chat_window, canvas_width // 2, canvas_height)


    def on_submit(self, event):
        text = self.input_entry.get().strip()
        if text:
            self.engine.apply_sentiment(text)
            self.update_chat()
            self.log_input(text)
        self.input_entry.delete(0, tk.END)

    def log_input(self, text):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")

    def update_loop(self):
        self.engine.update()
        self.root.after(50, self.update_loop)

    def run(self):
        self.root.mainloop()


def main():
    app = SentimentApp()
    app.run()


if __name__ == "__main__":
    main()
