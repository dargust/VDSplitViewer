############################
# Velocidrone Split Viewer # 
# Dan Argust 2025          #
############################
# velocidrone must be      #
# running or the websocket #
# will fail to connect and #
# the app will terminate   #
############################

import tkinter as tk
from tkinter import filedialog
import asyncio
import websockets
import json
import psutil
import win32gui
import pickle
import os
import logging
import sys
import requests
import tkinter.ttk as ttk

VERSION = "v0.3.3.1"

bbox = (0,0,0,0)
def callback(hwnd, extra):
    # callback function used by win32gui to get the window dimensions of velocidrone
    global bbox
    window_name = win32gui.GetWindowText(hwnd)
    if "velocidrone" == window_name:
        rect = win32gui.GetWindowRect(hwnd)
        x = rect[0]
        y = rect[1]
        w = rect[2] - x
        h = rect[3] - y
        print("{} window:".format(window_name))
        print("\tLocation: (%d, %d)" % (x, y))
        print("\t    Size: (%d, %d)" % (w, h))
        bbox = (x,y,w,h)

async def start_fake_messages(websocket):
    await websocket.send('serve')

async def send_heartbeat(websocket):
    # keep websocket connection alive
    try:
        while True:
            #print("sending heartbeat")
            await asyncio.sleep(10)
            await websocket.send("heartbeat")
    except Exception as e:
        print(f"Error sending heartbeat: {e}")

async def read_websocket(app):
    pl = app.pl # stores all the split times and data for all the players found or loaded
    first_run = True
    last_message = ""
    while True:
        try:
            async with websockets.connect(app.uri, ping_interval=None) as websocket:
                if first_run:
                    await start_fake_messages(websocket)
                    first_run = False
                heartbeat_task = asyncio.create_task(send_heartbeat(websocket))
                async for message in websocket:
                    if message == "done":
                        await websocket.send("stop")
                        first_run = False
                        break
                    if not message == last_message:
                        app.logger.info(message)
                    last_message = message
                    try:
                        f = json.loads(message)
                        if "racedata" in f:
                            for pilot,data in f['racedata'].items():
                                pl.process_racedata(pilot, data, app)
                        elif "countdown" in f:
                            countValue = f['countdown']['countValue']
                            if countValue == "0":
                                countValue = "Go!"
                            app.split_label.config(text=countValue, foreground="WHITE")
                            message = f"Countdown: {countValue}"
                            app.show_buttons(False)
                        elif "racestatus" in f:
                            raceAction = f['racestatus']['raceAction']
                            if raceAction == "race finished":
                                app.countdown_label.config(text="Stopped")
                                app.show_buttons(True)
                            app.racestatus_label.config(text=raceAction)
                            message = f"RaceStatus update: {raceAction}"
                        elif "racetype" in f:
                            raceMode = f['racetype']['raceMode']
                            raceFormat = f['racetype']['raceFormat']
                            raceLaps = f['racetype']['raceLaps']
                            app.racetype_label.config(text=f"{raceMode}, {raceFormat}, Laps: {raceLaps}")
                        else:
                            print("unhandled message:", f)
                    except json.JSONDecodeError as e:
                        pass#print(message)
                    except Exception as e:
                        print(e)
                    finally:
                        app.update_text(message)
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            await asyncio.sleep(1) # if something goes wrong with the connection, don't spam connection attempts
            print(e)

class Player():
    def __init__(self, name):
        self.name = name
        self.splits = {}
        self.comparison_splits = {}

class PlayerList():
    def __init__(self):
        self.list = []
        self.last_message_data = {}
        self.highest_gate = "0"
        self.highest_lap = "0"
        self.first_place_time = ""
        self.first_place_player = ""
        self.first_place_index = 0
        self.finished_list = []

    def get_index_of_player(self, player_name):
        j = 0
        for i in range(len(self.list)):
            j += 1
            if self.list[i].name == player_name:
                return(i)
        self.add_player_to_list(player_name)
        return(j)
    
    def add_player_to_list(self, player_name):
        self.list.append(Player(player_name))

    def number_to_hex_color(self, value):
        if value < 0: value = 0
        elif value > 1.5: value = 1.5

        # Normalize the value to be between 0 and 1
        normalized_value = value / 1.5

        # Calculate the red and green components
        red = 255
        green = int(255 * (1 - normalized_value / 1.2))  # Adjust the range for green component

        # Blue component is always 0 for the yellow to red gradient
        blue = int(100 * (1 - normalized_value))

        # Convert to hex
        hex_color = f'#{red:02x}{green:02x}{blue:02x}'
        return hex_color

    def process_racedata(self, player_name, data, app):
        #print(player_name, data)
        if player_name not in self.finished_list:
            if data['finished'] == "True":
                self.finished_list.append(player_name)
                app.add_copy_button(player_name, data['time'])
        if not data == self.last_message_data: # and player_name == app.target_player.get()
            i = self.get_index_of_player(player_name)
            gate = data['gate']
            lap = data['lap']
            time = data['time']
            position = int(data['position'])
            if position == 1 and app.options_var.get() == "Multiplayer: VS First Place":
                self.first_place_player = player_name
                self.first_place_index = self.get_index_of_player(self.first_place_player)
            uig = f"{lap}-{gate}"
            #print(player_name, position, uig, time)
            mp = True if app.options_var.get() == "Multiplayer: VS First Place" else False
            if player_name == app.target_player.get() and (not player_name == self.first_place_player or not mp):
                finished = True if data['finished'] == "True" else False
                self.list[i].splits[uig] = time
                try:
                    if app.options_var.get() == "Single Player: Time Attack":
                        old_time = float(self.list[i].comparison_splits[uig])
                    elif app.options_var.get() == "Multiplayer: VS First Place":
                        old_time = float(self.list[self.first_place_index].splits[uig])
                    elif app.options_var.get() == "Multiplayer: VS Rival":
                        old_time = float(self.list[self.first_place_index].splits[uig])
                    new_time = float(time)
                    if app.target_player.get() == player_name:
                        #print("latest personal time:", new_time)
                        split = new_time - old_time
                    colour = self.number_to_hex_color(split)
                    if split <= 0.0: colour = "light green"
                    if split <-1.5: colour = "green"
                    sign = "+" if split >= 0 else ""
                    #print("old time:", old_time, "new time:", new_time, "diff:", split)
                    app.split_label.config(text="{}{:.3f}".format(sign, split), foreground=colour)
                except Exception as e:
                    print(e)
                    app.split_label.config(text="{:.3f}".format(float(time)), foreground="WHITE")
                if finished:
                    if app.target_player.get() == player_name:
                        self.highest_gate = "0"
                        self.highest_lap = "0"
                        self.first_place_time = "0"
                    try:
                        if float(self.list[i].comparison_splits[uig]) > float(self.list[i].splits[uig]):
                            print("new pb, overwriting splits...")
                            #app.save_splits_button.configure(background="yellow")
                            app.style.configure('W.TButton', background="#555500")
                            self.list[i].comparison_splits = self.list[i].splits.copy()
                            app.pb = self.list[i].splits[uig]
                            app.open_file_time.config(text=f"PB: {app.pb}s")
                            if app.autosave.get() and app.open_file:
                                app.save_splits(app.open_file)

                    except KeyError as e:
                        print(e, "no comparison found, overwriting splits...")
                        #app.save_splits_button.configure(background="yellow")
                        app.style.configure('W.TButton', background="#555500")
                        self.list[i].comparison_splits = self.list[i].splits.copy()
                        app.pb = self.list[i].splits[uig]
                        app.open_file_time.config(text=f"PB: {app.pb}s")
                        if app.autosave.get() and app.open_file:
                            app.save_splits(app.open_file)
            self.list[i].splits[uig] = time
            if position == 2 and self.first_place_player == app.target_player.get():
                #print("second place: {}, first place: {}, comparison gate: {}".format(player_name, self.first_place_player, uig))
                new_time = float(time)
                old_time = float(self.list[self.first_place_index].splits[uig])
                split = old_time - new_time
                colour = self.number_to_hex_color(split)
                if split <= 0.0: colour = "light green"
                if split <-1.5: colour = "#4FC42C"
                sign = "+" if split >= 0 else ""
                app.split_label.config(text="{}{:.3f}".format(sign, split), foreground=colour)
            elif mp:
                pass
                #app.split_label.config(text=time, fg="BLUE")
        self.last_message_data = data
    
    def get_player_splits(self, player_name):
        i = self.get_index_of_player(player_name)
        return(self.list[i].comparison_splits)
    
    def set_player_splits(self, player_name, new_splits):
        i = self.get_index_of_player(player_name)
        self.list[i].comparison_splits = new_splits

class App(tk.Tk):
    def __init__(self, loop, interval=1/60):
        super().__init__()

        win32gui.EnumWindows(callback, None)
        print(bbox)

        self.loop = loop
        self.protocol("WM_DELETE_WINDOW", self.close) # unsure if necessary 
        self.tasks = []
        self.tasks.append(loop.create_task(self.updater(interval)))
        self.tasks.append(loop.create_task(read_websocket(self)))

        self.OFFSET = 0

        window_x = 520
        window_y = 900
        font_tuple = ("Consolas", 12, "normal")

        self.withdraw()
        self.wm_title("VDSplitViewer")
        x = int(bbox[0]+bbox[2]/2)-window_x//2
        y = bbox[1]+45
        self.geometry("+"+str(x)+"+"+str(y))

        self.overrideredirect(1) # makes the border around the window disappear

        self.attributes('-transparentcolor','#483269', '-topmost', 'True') # make all items with this colour transparent
        self.configure(background='#483269')

        self.resizable(0,0)

        local_appdata_path = os.getenv('LOCALAPPDATA')
        self.VDSplits_folder = os.path.join(local_appdata_path, "VDSplitviewerData")
        os.makedirs(self.VDSplits_folder, exist_ok=True)

        self.logger = logging.Logger('VDAppLogger')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        filehandler = logging.FileHandler(os.path.join(self.VDSplits_folder, 'messages.log'))
        filehandler.setFormatter(formatter)
        self.logger.addHandler(filehandler)

        self.style = ttk.Style()
        available_themes = self.style.theme_names()

        self.target_player = tk.StringVar()
        self.target_player.set("Enter player here")
        self.log_enabled = True
        self.race_director = False
        self.theme = "awdark"
        self.split_font_size = 18
        self.auto_hide = False
        self.config_file_path = os.path.join(self.VDSplits_folder, "config.txt")
        config_defaults = {'target player':'Enter player here', 'log enabled':True, 'race director':False, 'theme':'awdark', 'offset from top':0, 'font size':18, 'auto hide':False}
        try:
            if os.path.exists(self.config_file_path):
                cfg = json.load((open(self.config_file_path, "r")))
                self.target_player.set(cfg['target player'])
                self.log_enabled = cfg['log enabled']
                self.race_director = cfg['race director']
                self.theme = cfg['theme']
                self.OFFSET = cfg['offset from top']
                self.split_font_size = cfg['font size']
                self.auto_hide = cfg['auto hide']
            else:
                json.dump(config_defaults, open(self.config_file_path, "w"))
        except:
            print("Config file error, creating new one with default values")
            json.dump(config_defaults, open(self.config_file_path, "w"))
        
        if self.theme in available_themes:
            self.style.theme_use(self.theme)

        self.style.configure('TButton', font=font_tuple, padding=5)
        self.style.configure('TLabel', font=font_tuple, background='#483269', foreground='white')
        self.style.configure('TCheckbutton', font=font_tuple, background='#483269', foreground='white')
        self.style.configure('TEntry', font=font_tuple)
        self.default_background = self.style.lookup('TButton', 'background')
        self.style.configure('W.TButton', font=font_tuple, background=self.default_background)
        self.style.configure('Q.TButton', font=font_tuple, background='#555500')

        self.left_frame = tk.Frame(self, width=window_x, height=window_y, bg=self['bg'])
        self.left_frame.grid(rowspan=4, stick="ew")
        self.left_frame.grid_propagate(0)

        self.load_splits_button = ttk.Button(self.left_frame, text="Load", command=self.load_splits)
        self.load_splits_button.grid(column=0, row=0, sticky="w")
        self.save_splits_button = ttk.Button(self.left_frame, text="Save", command=self.save_splits, style='W.TButton')
        self.save_splits_button.grid(column=0, row=1, sticky="w")

        self.clear_splits_button = ttk.Button(self.left_frame, text="Clear", command=self.clear_splits)
        self.clear_splits_button.grid(column=0, row=2, sticky="w")

        self.close_button = ttk.Button(self.left_frame, text="Close", command=self.close)
        self.close_button.grid(column=3, row=0, sticky="e")

        self.open_file = ""

        self.open_file_label = ttk.Label(self.left_frame, text="Filename: NA")
        self.open_file_label.grid(row=3, column=0, columnspan=2, sticky="w")
        self.open_file_time = ttk.Label(self.left_frame, text="PB: -")
        self.open_file_time.grid(row=4, column=0, columnspan=1, sticky="w")
        self.autosave = tk.IntVar()
        self.autosave.set(1)
        self.auto_save_toggle = ttk.Checkbutton(self.left_frame, text="Autosave", variable=self.autosave)
        self.auto_save_toggle.grid(row=1, column=3, sticky="e")
        self.multiplayer = tk.IntVar()
        self.multiplayer.set(0)
        self.multiplayer_toggle = ttk.Checkbutton(self.left_frame, text="Multiplayer", variable=self.multiplayer, command=self.multiplayer_clicked)
        self.multiplayer_toggle.grid(row=2, column=3, sticky="e")
        self.options = ["Single Player: Time Attack", "Multiplayer: VS First Place"]
        self.options_var = tk.StringVar()
        self.options_var.set(self.options[0])
        self.multiplayer_target_options = ttk.Combobox(self, textvariable=self.options_var, values=self.options)
        self.multiplayer_target_options.config(font=font_tuple)

        self.logger.disabled = not self.log_enabled

        self.copy_frame = tk.Frame(self, bg=self['bg'])
        if self.race_director:
            self.copy_frame.grid(row=0, column=2, stick="nw")

        self.race_director_var = tk.IntVar()
        self.race_director_var.set(self.race_director)
        self.race_director_toggle = ttk.Checkbutton(self.left_frame, text="Race Director", variable=self.race_director_var, command=self.race_director_clicked)
        self.race_director_toggle.grid(row=3, column=3, sticky="e")

        self.target_player_entry = ttk.Entry(self.left_frame, textvariable=self.target_player, justify="center")
        self.target_player_entry.grid(row=4, column=3, columnspan=1)

        self.text = ttk.Label(self, text="Debug string")
        self.racetype_label = ttk.Label(self, text="Race type")
        self.racestatus_label = ttk.Label(self, text="Race status")
        self.countdown_label = ttk.Label(self, text="Countdown")
        self.pad_frame = tk.Frame(self.left_frame, bg=self['bg'], height=self.OFFSET)#self['bg'], height=OFFSET)
        self.pad_frame.grid(columnspan=4, stick="ns")
        self.split_label = ttk.Label(self.left_frame, text="VDSplitViewer", font=f"Consolas {self.split_font_size} bold", anchor="s")
        self.split_label.grid(columnspan=4, sticky="s")

        self.foundation_frame = tk.Frame(self.left_frame, bg=self['bg'], height=158)
        self.foundation_frame.grid(row=0, rowspan=5, column=5, stick="w")

        self.left_frame.grid_columnconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        localip = self.find_local_ip()
        self.uri = ""
        self.fake_messages = False
        if localip:
            self.uri = "ws://{}/velocidrone".format(localip)
            print(localip)
        else:
            print("WARNING!!! No velocidrone instance found, using fake messages")
            self.uri = "ws://localhost:8765"
            self.fake_messages = True
            self.geometry("+100+100")

        self.clear_copy_button = ttk.Button(self.copy_frame, text="Clear copy buttons", command=self.clear_copy_buttons)
        self.clear_copy_button.grid(sticky="nw")
        self.copy_button_list = []

        new_version_available = check_latest_version()
        if new_version_available:
            self.split_label.config(text="New version available")

        self.pl = PlayerList()
        self.pb = "-"
        self.deiconify()

    def clear_copy_buttons(self):
        for button in self.copy_button_list:
            button.destroy()
        self.copy_button_list = []
        self.pl.finished_list = []

    def clipboard_update(self, text, player):
        self.clipboard_clear()
        self.clipboard_append(text)
        for button in self.copy_button_list:
            if button.cget("text") == player:
                button.configure(style='TButton')

    def add_copy_button(self, player, time):
        self.copy_button_list.append(ttk.Button(self.copy_frame, text=f"{player}", style='Q.TButton', command=lambda: self.clipboard_update(str(time), player)))
        for button in self.copy_button_list:
            button.grid(sticky="nw")

    def show_multiplayer_target_options(self, show):
        if show:
            self.multiplayer_target_options.grid(row=0, column=1, sticky="nw")
        else:
            self.multiplayer_target_options.grid_forget()
    
    def multiplayer_clicked(self):
        self.show_multiplayer_target_options(self.multiplayer.get())

    def race_director_clicked(self):
        self.race_director = True if self.race_director_var.get() == 1 else False
        if self.race_director:
            self.copy_frame.grid(row=0, column=2, stick="nw")
        else:
            self.copy_frame.grid_forget()

    def load_splits(self, filename=None):
        if self.target_player.get() == "Enter player here":
            print("No player selected")
        else:
            json.dump({'target player':self.target_player.get()}, open(self.config_file_path, "w"))
            if not filename:
                file = filedialog.askopenfile("rb", initialdir=self.VDSplits_folder)
                self.open_file = file.name
                self.open_file_label.config(text=os.path.basename(file.name))
            else:
                file = open(filename, "rb")
            file_splits = pickle.load(file)
            self.pl.set_player_splits(self.target_player.get(), file_splits)
            self.pb = file_splits[[*file_splits.keys()][-1]]
            self.open_file_time.config(text=f"PB: {self.pb}s")
            self.split_label.config(text="-", foreground='WHITE')

    def save_splits(self, filename=None):
        if self.target_player.get() == "Enter player here":
            print("No player selected")
        else:
            json.dump({'target player':self.target_player.get(), 'log enabled':self.log_enabled, 'race director':self.race_director, 'theme':self.theme, 'offset from top':self.OFFSET, 'font size':self.split_font_size, 'auto hide': self.auto_hide}, open(self.config_file_path, "w"))
            if not filename:
                file = filedialog.asksaveasfile("wb", initialdir=self.VDSplits_folder)
                self.open_file = file.name
                self.open_file_label.config(text=os.path.basename(file.name))
            else:
                file = open(filename, "wb")
            pickle.dump(self.pl.get_player_splits(self.target_player.get()), file)
            self.style.configure('W.TButton', background=self.default_background)

    def clear_splits(self):
        self.pl.set_player_splits(self.target_player.get(), {})
        self.split_label.config(text="-", foreground='WHITE')
        self.open_file = None
        self.open_file_label.config(text="Filename: NA")
        self.open_file_time.config(text="PB: -")

    async def updater(self, interval): # used by one of the loop tasks to keep the tkinter window responsive
        while True:
            self.update()
            await asyncio.sleep(interval)
    
    def update_text(self, text):
        self.text.config(text=text)

    def find_local_ip(self):
        for conn in psutil.net_connections(kind='inet'):
            pid = conn.pid
            if pid:
                try:
                    process = psutil.Process(pid)
                    local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                    if process.name() == "velocidrone.exe":
                        if local_addr.endswith("60003"):
                            if not is_ipv6(conn.laddr.ip):
                                return local_addr
                            else:
                                return f"[{conn.laddr.ip}]:{conn.laddr.port}" if conn.laddr else "N/A"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        return None

    def show_buttons(self, show=True):
        if self.auto_hide:
            if show:
                self.load_splits_button.grid(column=0, row=0, sticky="w")
                self.save_splits_button.grid(column=0, row=1, sticky="w")
                self.clear_splits_button.grid(column=0, row=2, sticky="w")
                self.open_file_label.grid(row=3, column=0, columnspan=2, sticky="w")
                self.open_file_time.grid(row=4, column=0, columnspan=1, sticky="w")
                self.auto_save_toggle.grid(row=1, column=3, sticky="e")
                self.multiplayer_toggle.grid(row=2, column=3, sticky="e")
                self.race_director_toggle.grid(row=3, column=3, sticky="e")
                self.target_player_entry.grid(row=4, column=3, columnspan=1)
            else:
                self.load_splits_button.grid_forget()
                self.save_splits_button.grid_forget()
                self.clear_splits_button.grid_forget()
                self.open_file_label.grid_forget()
                self.open_file_time.grid_forget()
                self.auto_save_toggle.grid_forget()
                self.multiplayer_toggle.grid_forget()
                self.race_director_toggle.grid_forget()
                self.target_player_entry.grid_forget()

    def close(self):
        json.dump({'target player':self.target_player.get(), 'log enabled':self.log_enabled, 'race director':self.race_director, 'theme':self.theme, 'offset from top':self.OFFSET, 'font size':self.split_font_size, 'auto hide':self.auto_hide}, open(self.config_file_path, "w"))
        for task in self.tasks:
            task.cancel()
        self.loop.stop()
        self.destroy()

def print_version():
    print("Velocidrone Split Viewer")
    print(f"Version: {VERSION}")
    sys.exit(0)

def check_latest_version():
    url = "https://api.github.com/repos/dargust/VDSplitViewer/releases"
    try:
        response = requests.get(url)
        response.raise_for_status()
        tags = response.json()
        if tags:
            latest_tag = tags[0]['name']
            if VERSION not in latest_tag:
                print(f"New version available: {latest_tag}")
                return True
        else:
            print("No tags found in the repository.")
    except requests.RequestException as e:
        print(f"Error checking latest version: {e}")
    return False

def is_ipv6(addr):
    return ":" in addr

def main():
    if "--version" in sys.argv:
        print_version()
    else:
        loop = asyncio.get_event_loop()
        app = App(loop)
        loop.run_forever()
        loop.close()

if __name__ == "__main__":
    main()