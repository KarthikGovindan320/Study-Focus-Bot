# Ensure that the below libraries are installed prior to usage
# Some timings and options can be tinkered with by changing numeric values within the code. You are encouraged to try what works best for you

import cv2
import tkinter as tk
from PIL import Image, ImageTk
import time
from datetime import datetime, timedelta
from playsound import playsound
import threading
import sys

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

class FocusMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Study Focus Monitor")

        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self.block_close)
        self.root.bind('<Alt-F4>', self.force_close)
        self.root.bind('<Escape>', self.force_close)
        self.root.bind('<FocusOut>', self.refocus)

        self.video_capture = cv2.VideoCapture(0)

        self.canvas = tk.Label(root)
        self.canvas.pack()

        self.timer_label = tk.Label(root, text="Focus Timer: 00:00:00", font=("Helvetica", 24), bg="black", fg="white")
        self.timer_label.pack(pady=10)

        self.break_timer_label = tk.Label(root, text="Break Timer (Last 5 hrs): 00:00:00", font=("Helvetica", 20), bg="black", fg="white")
        self.break_timer_label.pack()

        self.break_label = tk.Label(root, text="Breaks (Last 5 hrs): 0", font=("Helvetica", 20), bg="black", fg="white")
        self.break_label.pack(pady=10)

        self.start_time = time.time()
        self.paused_time = 0
        self.last_pause = None
        self.running = True

        self.breaks = []
        self.break_start_time = None
        self.break_running = False
        self.break_elapsed = 0

        self.face_not_found = False
        self.no_face_start_time = None
        self.popup = None

        self.update()
        self.update_timer()

    def update(self):
        if self.popup:
            self.popup.lift()
            self.popup.attributes("-topmost", True)
        else:
            self.root.lift()
            self.root.attributes("-topmost", True)

        ret, frame = self.video_capture.read()
        if not ret:
            self.root.after(10, self.update)
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3)
        face_detected = len(faces) > 0

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        current_time = time.time()

        if not face_detected:
            if self.no_face_start_time is None:
                self.no_face_start_time = current_time
            elif current_time - self.no_face_start_time >= 5 and not self.face_not_found:
                self.face_not_found = True
                self.show_break_popup()
        else:
            self.no_face_start_time = None
            if self.face_not_found:
                self.face_not_found = False
                self.close_popup()
                self.show_return_popup()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.imgtk = imgtk
        self.canvas.configure(image=imgtk)

        self.root.after(10, self.update)

    def update_timer(self):
        if self.running:
            elapsed = int(time.time() - self.start_time - self.paused_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.timer_label.config(text=f"Focus Timer: {h:02d}:{m:02d}:{s:02d}")

        if self.break_running:
            current_break_duration = time.time() - self.break_start_time
            total_break = self.break_elapsed + current_break_duration
        else:
            total_break = self.break_elapsed

        h, m, s = int(total_break) // 3600, (int(total_break) % 3600) // 60, int(total_break) % 60
        self.break_timer_label.config(text=f"Break Timer (Last 5 hrs): {h:02d}:{m:02d}:{s:02d}")

        self.cleanup_breaks()
        self.break_label.config(text=f"Breaks (Last 5 hrs): {len(self.breaks)}")

        self.root.after(1000, self.update_timer)

    def pause_timer(self):
        self.running = False
        self.last_pause = time.time()
        self.break_start_time = time.time()
        self.break_running = True
        self.breaks.append({'start': datetime.now(), 'duration': 0})
        self.check_face_during_break()

    def resume_timer(self):
        if self.last_pause and self.break_start_time:
            paused_duration = time.time() - self.last_pause
            break_duration = time.time() - self.break_start_time

            self.paused_time += paused_duration
            self.break_elapsed += break_duration

            if self.breaks:
                self.breaks[-1]['duration'] = break_duration

        self.running = True
        self.break_running = False
        self.last_pause = None
        self.break_start_time = None

    def cleanup_breaks(self):
        cutoff = datetime.now() - timedelta(hours=5)
        self.breaks = [b for b in self.breaks if b['start'] > cutoff]

    def show_break_popup(self):
        if not self.popup:
            self.popup = tk.Toplevel(self.root)
            self.popup.title("Confirm Break")
            self.popup.attributes("-topmost", True)
            self.popup.geometry("400x200+600+400")

            self.break_countdown_value = 10

            self.popup_label = tk.Label(
                self.popup,
                text=f"Face not found. Break in {self.break_countdown_value} sec.\nPlease focus b*@ch.",
                font=("Helvetica", 14),
                bg="white"
            )
            self.popup_label.pack(pady=20)

            self.no_button = tk.Button(self.popup, text="No", font=("Helvetica", 12), command=self.cancel_break)
            self.no_button.pack(pady=10)

            threading.Thread(target=self.play_sound, args=("notification.wav",), daemon=True).start()
            self.break_countdown()

    def break_countdown(self):
        if self.break_countdown_value > 0:
            self.popup_label.config(
                text=f"Face not found. Break in {self.break_countdown_value} sec.\nPlease focus"
            )
            self.break_countdown_value -= 1
            self.root.after(1000, self.break_countdown)
        else:
            self.trigger_break()

    def cancel_break(self):
        self.no_face_start_time = None
        self.face_not_found = False
        self.close_popup()

    def trigger_break(self):
        self.pause_timer()
        threading.Thread(target=self.play_sound, args=("break.wav",), daemon=True).start()
        self.close_popup()

    def show_return_popup(self):
        if not self.popup:
            self.popup = tk.Toplevel(self.root)
            self.popup.title("Back on Focus")
            self.popup.attributes("-topmost", True)
            self.popup.geometry("300x150+650+450")

            label = tk.Label(self.popup, text="Face detected.\nBack on focus?", font=("Helvetica", 14))
            label.pack(pady=10)
            button = tk.Button(self.popup, text="Back on focus", command=self.resume_and_close)
            button.pack(pady=10)

    def close_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None

    def resume_and_close(self):
        self.resume_timer()
        self.close_popup()

    def play_sound(self, file):
        try:
            playsound(file)
        except Exception as e:
            print(f"Sound error: {e}")

    def block_close(self):
        pass

    def force_close(self, event=None):
        print("Exiting...")
        self.root.destroy()
        if self.video_capture.isOpened():
            self.video_capture.release()
        cv2.destroyAllWindows()
        sys.exit()

    def refocus(self, event=None):
        if not self.popup:
            print("Focus lost. Forcing back...")
            self.root.attributes('-topmost', True)
            self.root.focus_force()
            self.root.deiconify()

    def check_face_during_break(self):
        if self.break_running and not self.popup:
            ret, frame = self.video_capture.read()
            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3)
                if len(faces) > 0:
                    self.show_return_popup()

        if self.break_running:
            self.root.after(2000, self.check_face_during_break)

if __name__ == "__main__":
    root = tk.Tk()
    app = FocusMonitor(root)
    root.mainloop()
