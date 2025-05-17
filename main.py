# coding: utf8

import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, PhotoImage
import sounddevice as sd
import wavio
import threading
import time
import requests
import json
import os
from pathlib import Path
import numpy as np
import base64
from io import BytesIO
from PIL import Image, ImageTk  # You'll need to install pillow if not already installed


USER_HOME = str(Path.home())
CONFIG_DIR = os.path.join(USER_HOME, '.config', 'TTS_UI')
TEMP_DIR = os.path.join(USER_HOME, '.tmp', 'TTS_UI')

# Create directories if they don't exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
AUDIO_FILE = os.path.join(TEMP_DIR, 'recorded.wav')

class STT_App:
    def __init__(self, root):
        # Add these lines to store the icons as instance attributes
        self.copy_icon = None
        self.tick_icon = None

        self.long_press = False
        self.press_start_time = 0
        self.long_press_threshold = 0.8  # seconds

        self.root = root
        self.root.title("Speech to Text UI")
        self.root.geometry("700x600")
        
        # Apply a modern theme with custom styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors for a modern look - updated color scheme
        bg_color = '#f8f9fa'
        accent_color = '#4361ee'
        text_color = '#212529'
        button_bg = '#e9ecef'
        button_active = '#4361ee'
        record_active_color = '#ff6b6b'  # Mild red color for recording
        
        
        # Configure styles with rounded corners and modern colors
        style.configure('TFrame', background=bg_color)
        style.configure('TLabelframe', background=bg_color)
        style.configure('TLabelframe.Label', background=bg_color, foreground=text_color, font=('Arial', 10))
        
        # Button styling - more modern with rounded corners
        style.configure('TButton', 
                        background=button_bg, 
                        foreground=text_color, 
                        borderwidth=0,
                        focusthickness=0, 
                        focuscolor=accent_color,
                        padding=10,
                        font=('Arial', 10))
        
        # Add a Recording button style
        style.configure('Recording.TButton', 
                    background=record_active_color,
                    foreground='white',
                    padding=10,
                    font=('Arial', 10, 'bold'))
        
        style.map('Recording.TButton',
                background=[('active', '#e05d5d'), ('pressed', '#d04f4f')],
                foreground=[('active', 'white'), ('pressed', 'white')])
        
        # Create rounded button style
        style.map('TButton',
                 background=[('active', button_active), ('pressed', button_active)],
                 foreground=[('active', 'white'), ('pressed', 'white')])
        
        # Primary button style (for record button)
        style.configure('Primary.TButton', 
                      background=accent_color,
                      foreground='white',
                      padding=10,
                      font=('Arial', 10, 'bold'))
        
        style.map('Primary.TButton',
                background=[('active', '#3a56d4'), ('pressed', '#2a46c4')],
                foreground=[('active', 'white'), ('pressed', 'white')])
        
        # Label styling
        style.configure('TLabel', background=bg_color, foreground=text_color, font=('Arial', 10))
        
        # Status label styling
        style.configure('Status.TLabel', background=bg_color, foreground=accent_color, font=('Arial', 10, 'italic'))

        # Entry styling
        style.configure('TEntry', fieldbackground='white', borderwidth=1)

        self.recording = False
        self.fs = 16000  # Sample rate
        self.frames = []
        self.record_thread = None
        self.timeout = 30  # Default timeout seconds
        self.audio_device_index = None  # προεπιλογή (system default)


        self.model_name = "whisper-1"
        self.api_base_url = ""
        self.api_token = ""

        self.load_config()
         # Initialize icons before creating widgets
        self.copy_icon = self.get_copy_icon()
        self.tick_icon = self.get_tick_icon()

        self.create_widgets()

        # Add keyboard shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts for the application"""
        # Ctrl+R to start/stop recording
        self.root.bind('<Control-r>', lambda event: self.toggle_recording())
        
        # Add a keyboard shortcut indicator to the record button tooltip
        self.create_tooltip(self.btn_record, "Start/Stop Recording (Ctrl+R)")


    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # MODEL LABEL (read-only display on top)
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill=tk.X, pady=(0,5))
        ttk.Label(model_frame, text="Model:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.label_model = ttk.Label(model_frame, text=self.model_name, font=("Arial", 10))
        self.label_model.pack(side=tk.LEFT, padx=(5,0))

        # TOGGLE CONFIG BUTTON
        self.btn_toggle_config = ttk.Button(frame, text="Show Config", command=self.toggle_config)
        self.btn_toggle_config.pack(fill=tk.X, pady=(0,10))

        # CONFIG FRAME (hidden initially)
        self.config_frame = ttk.LabelFrame(frame, text="API Configuration")


        ttk.Label(self.config_frame, text="Base URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_base_url = ttk.Entry(self.config_frame, width=60)
        self.entry_base_url.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.entry_base_url.insert(0, self.api_base_url)

        ttk.Label(self.config_frame, text="API Token:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_api_token = ttk.Entry(self.config_frame, width=60, show="*")
        self.entry_api_token.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.entry_api_token.insert(0, self.api_token)

        ttk.Label(self.config_frame, text="Model:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_model = ttk.Entry(self.config_frame, width=20, state='normal')
        self.entry_model.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.entry_model.delete(0, tk.END)
        self.entry_model.insert(0, self.model_name)

        # Timeout
        ttk.Label(self.config_frame, text="Timeout (s):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_timeout = ttk.Entry(self.config_frame, width=10)
        self.entry_timeout.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        self.entry_timeout.insert(0, str(self.timeout))

        # Audio Input Device Selection
        ttk.Label(self.config_frame, text="Mic Device:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.combo_device = ttk.Combobox(self.config_frame, state="readonly", width=50)
        self.combo_device.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        self.populate_audio_devices()

        # Move save button after audio settings
        btn_save = ttk.Button(self.config_frame, text="Save Config", command=self.save_config)
        btn_save.grid(row=5, column=1, sticky=tk.E, padx=5, pady=5)

        # RECORD BUTTON - modified to use button press/release events only
        self.btn_record = ttk.Button(frame, text="Start Recording (Ctrl+R)", style="Primary.TButton")
        self.btn_record.pack(pady=10)

        # Remove the command from the button and just use our press/release events
        self.btn_record.bind("<ButtonPress-1>", self.on_record_button_press)
        self.btn_record.bind("<ButtonRelease-1>", self.on_record_button_release)
        
        # STATUS LABEL (shows recording status)
        self.label_status = ttk.Label(frame, text="", style="Status.TLabel")
        self.label_status.pack()

        # TRANSCRIBE TEXT AREA - MODIFIED
        transcribe_frame = ttk.LabelFrame(frame, text="Transcribed Text")
        transcribe_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add buttons for Clear, Save, and Load transcriptions
        transcription_actions_frame = ttk.Frame(transcribe_frame)
        transcription_actions_frame.pack(fill=tk.X, padx=5, pady=(5,0))
        
        self.btn_clear = ttk.Button(transcription_actions_frame, text="Clear All", command=self.clear_transcriptions)
        self.btn_clear.pack(side=tk.LEFT, padx=(0,5))
        self.create_tooltip(self.btn_clear, "Clear all transcriptions")
        
        self.btn_save = ttk.Button(transcription_actions_frame, text="Save", command=self.save_transcriptions)
        self.btn_save.pack(side=tk.LEFT, padx=5)
        self.create_tooltip(self.btn_save, "Save transcriptions to JSON file")
        
        self.btn_load = ttk.Button(transcription_actions_frame, text="Load", command=self.load_transcriptions)
        self.btn_load.pack(side=tk.LEFT, padx=5)
        self.create_tooltip(self.btn_load, "Load transcriptions from JSON file")

        # Create a scrollable canvas to hold multiple transcription entries
        self.canvas_frame = ttk.Frame(transcribe_frame)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create canvas
        self.canvas = tk.Canvas(self.canvas_frame, yscrollcommand=scrollbar.set, background="#ffffff", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        scrollbar.config(command=self.canvas.yview)
        
        # Create a frame inside the canvas to hold the transcription entries
        self.transcriptions_container = ttk.Frame(self.canvas, style='TFrame')
        self.canvas_window = self.canvas.create_window((0, 0), window=self.transcriptions_container, anchor=tk.NW, width=self.canvas.winfo_reqwidth())
        
        # Make sure the canvas resizes with the window
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.transcriptions_container.bind('<Configure>', self.on_transcriptions_container_configure)
        
        # List to keep track of all transcription entries
        self.transcription_entries = []

        # Hide config frame initially
        self.config_visible = False

    def clear_transcriptions(self):
        """Clear all transcription entries"""
        if not self.transcription_entries:
            messagebox.showinfo("Info", "No transcriptions to clear.")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all transcriptions?"):
            # Remove all transcription frames
            for entry in self.transcription_entries:
                entry['frame'].destroy()
            
            # Clear the list
            self.transcription_entries = []
            
            # Update the canvas
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            self.label_status.config(text="All transcriptions cleared.")



    def save_transcriptions(self):
        """Save all transcriptions to a JSON file"""
        if not self.transcription_entries:
            messagebox.showinfo("Info", "No transcriptions to save.")
            return
        
        from tkinter import filedialog
        
        # Prepare data for saving
        transcription_data = []
        for entry in self.transcription_entries:
            transcription_data.append({
                'text': entry['text'],
                'timestamp': entry['timestamp'],
            })
        
        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Transcriptions"
        )
        
        if not file_path:
            return  # User canceled
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("Success", f"Transcriptions saved to {file_path}")
            self.label_status.config(text=f"Transcriptions saved to {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save transcriptions:\n{e}")

    def load_transcriptions(self):
        """Load transcriptions from a JSON file"""
        from tkinter import filedialog
        
        # Ask user for file to load
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Transcriptions"
        )
        
        if not file_path:
            return  # User canceled
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transcription_data = json.load(f)
            
            # Clear existing transcriptions first
            if self.transcription_entries:
                if not messagebox.askyesno("Confirm", "This will replace all current transcriptions. Continue?"):
                    return
                self.clear_transcriptions()
            
            # Add loaded transcriptions
            for item in transcription_data:
                self.display_transcription(item['text'], item.get('timestamp'))
            
            messagebox.showinfo("Success", f"Loaded {len(transcription_data)} transcriptions from {file_path}")
            self.label_status.config(text=f"Transcriptions loaded from {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transcriptions:\n{e}")


    def on_canvas_configure(self, event):
        # Update the scrollregion when the canvas size changes
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def on_transcriptions_container_configure(self, event):
        # Update the scroll region when the content size changes
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def on_record_button_press(self, event):
        self.press_start_time = time.time()
        
        # If already recording, stop recording immediately
        if self.recording:
            self.stop_recording()
        else:
            # Otherwise, start recording immediately
            self.start_recording()

    def check_long_press(self):
        # If button is still being pressed after threshold time
        if hasattr(self, 'press_start_time') and time.time() - self.press_start_time >= self.long_press_threshold:
            if not self.recording:
                self.long_press = True
                self.start_recording()

    def on_record_button_release(self, event):
        if not self.recording:
            # If we're not recording at release time, do nothing
            return
            
        press_duration = time.time() - self.press_start_time
        
        # Only stop recording if the press duration exceeds threshold
        if press_duration >= self.long_press_threshold:
            # This was a long press, stop recording
            self.stop_recording()
        else:
            # For short presses, do nothing (keep recording)
            pass
            
    def toggle_config(self):
        if self.config_visible:
            self.config_frame.pack_forget()
            self.btn_toggle_config.config(text="Show Config")
            self.config_visible = False
        else:
            # Place the config frame after the button but before other elements
            self.config_frame.pack(fill=tk.X, pady=5, after=self.btn_toggle_config)
            self.btn_toggle_config.config(text="Hide Config")
            self.config_visible = True
            
            # Ensure the window can fit all content
            self.root.update_idletasks()  # Update layout
            content_height = sum(child.winfo_reqheight() for child in self.root.winfo_children())
            current_width = self.root.winfo_width()
            self.root.geometry(f"{current_width}x{max(content_height + 50, 600)}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                self.api_base_url = data.get('base_url', '')
                self.api_token = data.get('api_token', '')
                self.model_name = data.get('model', self.model_name)
                try:
                    self.timeout = int(data.get('timeout', 60))
                except ValueError:
                    self.timeout = 60
                self.audio_device_index = data.get('audio_device_index', None)
            except Exception as e:
                print(f"Failed to load config from {CONFIG_FILE}:", e)

    def save_config(self):
        base_url = self.entry_base_url.get().strip()
        token = self.entry_api_token.get().strip()
        model = self.entry_model.get().strip()
        timeout = self.entry_timeout.get().strip()

        if not base_url or not token:
            messagebox.showerror("Error", "Base URL and API Token cannot be empty.")
            return
        if not model:
            messagebox.showerror("Error", "Model cannot be empty.")
            return

        data = {
            "base_url": base_url,
            "api_token": token,
            "model": model,
            "timeout": timeout,
            "audio_device_index": self.audio_device_index
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
            self.api_base_url = base_url
            self.api_token = token
            self.model_name = model

            # Ενημερώνουμε και την ετικέτα που δείχνει το μοντέλο πάνω
            self.label_model.config(text=self.model_name)

            messagebox.showinfo("Saved", "Configuration saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config file:\n{e}")

    def toggle_recording(self):
        # Only use toggle for short presses or keyboard shortcuts
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if not self.api_base_url or not self.api_token:
            messagebox.showerror("Config Missing", "Please configure API Base URL and Token first and save.")
            return
        self.recording = True
        self.btn_record.config(text="Stop Recording (Ctrl+R)", style="Recording.TButton")  # Change to red style
        self.frames = []
        
        self.label_status.config(text="Recording... 0 s")
        self.record_start_time = time.time()
        self.record_thread = threading.Thread(target=self.record_audio, daemon=True)
        self.record_thread.start()
        self.update_recording_time()


    def stop_recording(self):
        self.recording = False
        self.btn_record.config(text="Start Recording (Ctrl+R)", style="Primary.TButton")  # Change back to primary style
        self.label_status.config(text="Processing recording...")

    def update_recording_time(self):
        if self.recording:
            elapsed = int(time.time() - self.record_start_time)
            self.label_status.config(text=f"Recording... {elapsed} s")
            self.root.after(500, self.update_recording_time)

    def record_audio(self):
        try:
            with sd.InputStream(samplerate=self.fs, channels=1, dtype='int16', callback=self.audio_callback):
                while self.recording:
                    sd.sleep(100)
            if len(self.frames) == 0:
                self.root.after(0, lambda: messagebox.showwarning("Warning", "No audio recorded."))
                return
            audio_data_bytes = b''.join(self.frames)
            data_np = np.frombuffer(audio_data_bytes, dtype='int16')
            wavio.write(AUDIO_FILE, data_np, self.fs, sampwidth=2)
            self.root.after(0, self.transcribe_audio)

        except Exception as e:
            self.recording = False
            self.root.after(0, lambda: messagebox.showerror("Error", f"Recording failed:\n{e}"))
            self.root.after(0, lambda: self.btn_record.config(text="Start Recording"))
            self.label_status.config(text="Recording failed.")

    def audio_callback(self, indata, frames, time_, status):
        if status:
            print(f"InputStream status: {status}")
        self.frames.append(indata.copy().tobytes())

    def transcribe_audio(self):
        # We don't need to modify any text widget here anymore since we're 
        # creating new text widgets for each transcription
        # Just update the status and start the transcription thread
        self.label_status.config(text="Transcribing audio...")
        threading.Thread(target=self._transcribe_thread, daemon=True).start()

    def _transcribe_thread(self):
        try:
            with open(AUDIO_FILE, 'rb') as f:
                files = {
                    'file': (AUDIO_FILE, f, 'audio/wav')
                }
                headers = {
                    'Authorization': f'Bearer {self.api_token}'
                }
                url = self.api_base_url.rstrip('/') + "/v1/audio/transcriptions"
                data = {
                    "model": self.model_name
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=self.timeout)
                if response.status_code == 200:
                    json_resp = response.json()
                    text = json_resp.get('text', '')
                    self.root.after(0, lambda: self.display_transcription(text))
                else:
                    try:
                        err = response.json()
                    except Exception:
                        err = response.text
                    self.root.after(0, lambda: messagebox.showerror("API Error", f"Status {response.status_code}:\n{err}"))
        except Exception as e:
            self.root.after(0, lambda e=e: messagebox.showerror("Transcription Failed", str(e)))
        finally:
            if os.path.exists(AUDIO_FILE):
                try:
                    os.remove(AUDIO_FILE)
                except Exception:
                    pass

    
    def display_transcription(self, text, timestamp=None):
        # Use provided timestamp or create a new one
        if timestamp is None:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
        
        # Create a new frame for this transcription entry
        entry_frame = ttk.Frame(self.transcriptions_container)
        entry_frame.pack(fill=tk.X, expand=True, pady=(0, 5), padx=5)
        
        # Add a header with timestamp
        header_frame = ttk.Frame(entry_frame)
        header_frame.pack(fill=tk.X, expand=True)
        
        # Add timestamp label
        timestamp_label = ttk.Label(header_frame, text=f"[{timestamp}]", 
                                font=("Arial", 9, "italic"), foreground="#666666")
        timestamp_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Add copy button for this entry
        if self.copy_icon is None:
            self.copy_icon = self.get_copy_icon()
        copy_btn = ttk.Button(header_frame, image=self.copy_icon, 
                    command=lambda t=text: self.copy_specific_text(t))
        copy_btn.pack(side=tk.RIGHT, padx=5)
        self.create_tooltip(copy_btn, "Copy this transcription")
        
        # Add text area for the transcription
        text_frame = ttk.Frame(entry_frame, padding=5)
        text_frame.pack(fill=tk.X, expand=True)
        
        # Create a text widget with rounded corners and border
        text_widget = tk.Text(text_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            padx=10, pady=10, background="#ffffff", borderwidth=1,
                            relief=tk.SOLID)
        text_widget.pack(fill=tk.X, expand=True)
        text_widget.insert(tk.END, text)
        text_widget.config(state=tk.DISABLED)
        
        # Add a separator
        ttk.Separator(entry_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, expand=True, pady=(5, 0))
        
        # Store the entry information
        self.transcription_entries.append({
            'frame': entry_frame,
            'text': text,
            'text_widget': text_widget,
            'copy_button': copy_btn,
            'timestamp': timestamp
        })
        
        # Scroll to show the new entry
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)
        
        # Update status
        self.label_status.config(text="Transcription completed.")
        
        # Copy the latest text to clipboard for convenience
        if text.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            
            # Provide visual feedback
            self.tick_icon = self.get_tick_icon()
            if self.tick_icon:
                copy_btn.config(image=self.tick_icon)
                self.root.after(2000, lambda btn=copy_btn: btn.config(image=self.copy_icon))
        
        # Make sure we're not in recording state when transcription completes
        self.recording = False
        self.btn_record.config(text="Start Recording (Ctrl+R)")

    def copy_specific_text(self, text):
        """Copy a specific transcription text to clipboard"""
        if text.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            # messagebox.showinfo("Copied", "Transcription copied to clipboard")


    def copy_to_clipboard(self):
        """This method is now used to copy all transcriptions"""
        if not self.transcription_entries:
            messagebox.showinfo("No Text", "There are no transcriptions to copy.")
            return
            
        # Concatenate all transcription texts
        all_text = "\n".join([f"[{entry['timestamp']}] {entry['text']}" for entry in self.transcription_entries])
        
        self.root.clipboard_clear()
        self.root.clipboard_append(all_text)
        
        # Show feedback
        messagebox.showinfo("Copied", "All transcriptions copied to clipboard!")

    def populate_audio_devices(self):
        devices = sd.query_devices()
        input_devices = []
        self.device_index_map = {}  # όνομα -> index

        for idx, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                name = f"{device['name']} (ID {idx})"
                input_devices.append(name)
                self.device_index_map[name] = idx

        self.combo_device['values'] = input_devices

        # Επιλογή αποθηκευμένης ή default
        selected_name = None
        if self.audio_device_index is not None:
            for name, idx in self.device_index_map.items():
                if idx == self.audio_device_index:
                    selected_name = name
                    break
        if selected_name:
            self.combo_device.set(selected_name)
        elif input_devices:
            self.combo_device.current(0)
            self.audio_device_index = self.device_index_map[input_devices[0]]
        else:
            self.combo_device.set('No input device found')
            self.audio_device_index = None

    def create_tooltip(self, widget, text):
        def enter(event):
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = ttk.Label(self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
            label.pack()
            
        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def get_copy_icon(self):
        try:    
            # Use PIL for resizing
            from PIL import Image, ImageTk
            
            # Set your desired pixel size here
            desired_width, desired_height = 24, 24
            
            # Open the image
            img = Image.open( self.resource_path("assets/copy.png") )
            
            # Handle different Pillow versions for resampling
            try:
                # For newer Pillow versions (9.0+)
                from PIL import Resampling
                img = img.resize((desired_width, desired_height), Resampling.BICUBIC)
            except (ImportError, AttributeError):
                print("Error using Pillow - copy-icon")
                # For older Pillow versions
                img = img.resize((desired_width, desired_height), 3)  # 3 is the integer value for BICUBIC
            
            # Convert to PhotoImage
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading copy icon: {e}")
            return None

    def get_tick_icon(self):
        try:
            # Check if file exists first
            # if not os.path.exists('assets/tick.png'):
            #     print("Tick icon file not found")
            #     return None
                
            # Use PIL for resizing
            from PIL import Image, ImageTk
            
            # Set your desired pixel size here
            desired_width, desired_height = 24, 24
            
            # Open the image
            # img = Image.open('assets/tick.png')
            img = Image.open( self.resource_path("assets/tick.png") )

            # Handle different Pillow versions for resampling
            try:
                # For newer Pillow versions (9.0+)
                from PIL import Resampling
                img = img.resize((desired_width, desired_height), Resampling.BICUBIC)
            except (ImportError, AttributeError):
                print("Error using Pillow - correct-icon")
                # For older Pillow versions
                img = img.resize((desired_width, desired_height), 3)  # 3 is the integer value for BICUBIC
            
            # Convert to PhotoImage
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading tick icon: {e}")
            return None
        
    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(os.path.dirname(__file__))
        path = os.path.join(base_path, relative_path)
        return path

def main():
    root = tk.Tk()
    app = STT_App(root)

    try:
        from version import __version__
    except ImportError:
        __version__ = "dev"
    
    # Add version label on the right side
    version_label = tk.Label(root, text=f"v{__version__}", fg="gray")
    version_label.pack(side=tk.RIGHT, padx=10)

    root.mainloop()

if __name__ == "__main__":
    main()