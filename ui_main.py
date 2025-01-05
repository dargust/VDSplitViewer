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

# callback function used by win32gui to get the window dimensions of velocidrone
bbox = (0,0,0,0)
def callback(hwnd, extra):
    global bbox
    if "velocidrone" in win32gui.GetWindowText(hwnd):
        rect = win32gui.GetWindowRect(hwnd)
        x = rect[0]
        y = rect[1]
        w = rect[2] - x
        h = rect[3] - y
        print("Window %s:" % win32gui.GetWindowText(hwnd))
        print("\tLocation: (%d, %d)" % (x, y))
        print("\t    Size: (%d, %d)" % (w, h))
        bbox = (x,y,w,h)

# keep websocket connection alive
async def send_heartbeat(websocket):
    try:
        while True:
            await asyncio.sleep(10)
            await websocket.send("heartbeat")
    except Exception as e:
        print(f"Error sending heartbeat: {e}")

async def read_websocket(app):
    pl = app.pl # stores all the split times and data for all the players found or loaded
    while True:
        try:
            async with websockets.connect(app.uri, ping_interval=None) as websocket:
                heartbeat_task = asyncio.create_task(send_heartbeat(websocket))
                async for message in websocket:
                    try:
                        f = json.loads(message)
                        if "racedata" in f:
                            for pilot,data in f['racedata'].items():
                                pl.process_racedata(pilot, data, app)
                        elif "countdown" in f:
                            countValue = f['countdown']['countValue']
                            if countValue == "0":
                                countValue = "Go!"
                            app.split_label.config(text=countValue, fg="WHITE")
                            message = f"Countdown: {countValue}"
                        elif "racestatus" in f:
                            raceAction = f['racestatus']['raceAction']
                            if raceAction == "race finished":
                                app.countdown_label.config(text="Stopped")
                            app.racestatus_label.config(text=raceAction)
                            message = f"RaceStatus update: {raceAction}"
                        elif "racetype" in f:
                            raceMode = f['racetype']['raceMode']
                            raceFormat = f['racetype']['raceFormat']
                            raceLaps = f['racetype']['raceLaps']
                            app.racetype_label.config(text=f"{raceMode}, {raceFormat}, Laps: {raceLaps}")
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

    def process_racedata(self, player_name, data, app):
        if not data == self.last_message_data:
            i = self.get_index_of_player(player_name)
            gate = data['gate']
            lap = data['lap']
            time = data['time']
            uig = f"{lap}-{gate}"
            finished = True if data['finished'] == "True" else False
            self.list[i].splits[uig] = time
            try:
                old_time = float(self.list[i].comparison_splits[uig])
                new_time = float(time)
                split = new_time - old_time
                colour = "red"
                if split < 1.5: colour = "yellow"
                if split <= 0.0: colour = "light green"
                if split <-1.5: colour = "green"
                app.split_label.config(text="{:.3f}".format(split), fg=colour)
            except:
                app.split_label.config(text="{:.3f}".format(float(time)))
            if finished:
                try:
                    if float(self.list[i].comparison_splits[uig]) > float(self.list[i].splits[uig]):
                        print("new pb, overwriting splits...")
                        app.save_splits_button.configure(bg="yellow")
                        self.list[i].comparison_splits = self.list[i].splits.copy()
                        app.pb = self.list[i].splits[uig]
                        app.open_file_time.config(text=f"PB: {app.pb}s")
                        if app.autosave.get() and app.open_file:
                            app.save_splits(app.open_file)

                except KeyError as e:
                    print(e, "no comparison found, overwriting splits...")
                    app.save_splits_button.configure(bg="yellow")
                    self.list[i].comparison_splits = self.list[i].splits.copy()
                    app.pb = self.list[i].splits[uig]
                    app.open_file_time.config(text=f"PB: {app.pb}s")
                    if app.autosave.get() and app.open_file:
                        app.save_splits(app.open_file)
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

        window_x = 510
        window_y = 160
        font_tuple = ("Consolas", 12, "normal")

        self.withdraw()
        self.wm_title("VDSplitViewer")
        x = int(bbox[0]+bbox[2]/2)-window_x//2
        y = bbox[1]+45
        self.geometry(str(window_x)+"x"+str(window_y)+"+"+str(x)+"+"+str(y))
    
        self.overrideredirect(1) # makes the border around the window disappear

        self.attributes('-transparentcolor','#483269', '-topmost', 'True') # make all items with this colour transparent
        self.configure(background='#483269')

        self.resizable(0,0)

        local_appdata_path = os.getenv('LOCALAPPDATA')
        self.VDSplits_folder = os.path.join(local_appdata_path, "VDSplitviewerData")
        os.makedirs(self.VDSplits_folder, exist_ok=True)

        self.load_splits_button = tk.Button(self, text="Load", height=1, width=9, font=font_tuple, command=self.load_splits)
        self.load_splits_button.grid(column=0, row=0, sticky="w")
        self.save_splits_button = tk.Button(self, text="Save", height=1, width=9, font=font_tuple, command=self.save_splits)
        self.save_splits_button.grid(column=0, row=1, sticky="w")

        self.clear_splits_button = tk.Button(self, text="Clear", height=1, width=9, font=font_tuple, command=self.clear_splits)
        self.clear_splits_button.grid(column=3, row=1, sticky="e")

        self.close_button = tk.Button(self, text="Close", height=1, width=9, font=font_tuple, command=self.close)
        self.close_button.grid(column=3, row=0, sticky="e")

        self.open_file = ""

        self.open_file_label = tk.Label(self, text="Filename: NA", font=font_tuple, fg='WHITE', bg=self['bg'])
        self.open_file_label.grid(row=2, column=0, columnspan=2, sticky="w")
        self.open_file_time = tk.Label(self, text="PB: -", font=font_tuple, fg='WHITE', bg=self['bg'])
        self.open_file_time.grid(row=3, column=0, columnspan=1, sticky="w")
        self.autosave = tk.IntVar()
        self.autosave.set(1)
        self.auto_save_toggle = tk.Checkbutton(self, text="Autosave", height=1, width=9, variable=self.autosave, anchor="w", font=font_tuple)#, fg='WHITE', bg=self['bg'])
        self.auto_save_toggle.grid(row=2, column=3, sticky="e")

        self.target_player = tk.StringVar()
        self.target_player.set("Enter player here")
        self.config_file_path = os.path.join(self.VDSplits_folder, "config.txt")
        if os.path.exists(self.config_file_path):
            cfg = json.load((open(self.config_file_path, "r")))
            self.target_player.set(cfg['target player'])
        else:
            json.dump({'target player':'Enter player here'}, open(self.config_file_path, "w"))
        self.target_player_entry = tk.Entry(self, textvariable=self.target_player, justify="center", font=font_tuple)
        self.target_player_entry.grid(row=3, column=3, columnspan=1)

        #temporary or debugging labels are commented out, they still exist put are not placed on the window

        self.text = tk.Label(self, text="Debug string", font=font_tuple,fg='WHITE', bg=self['bg'])
        #self.text.grid(row=4, columnspan=4)

        self.racetype_label = tk.Label(self, text="Race type", font=font_tuple, fg='WHITE', bg=self['bg'])
        #self.racetype_label.grid(columnspan=4)

        self.racestatus_label = tk.Label(self, text="Race status", font=font_tuple, fg='WHITE', bg=self['bg'])
        #self.racestatus_label.grid(columnspan=4)

        self.countdown_label = tk.Label(self, text="Countdown", font=font_tuple, fg='WHITE', bg=self['bg'])
        #self.countdown_label.grid(columnspan=4)

        self.split_label = tk.Label(self, text="Splits", font="Consolas 18 bold", fg='WHITE', bg=self['bg'])
        self.split_label.grid(columnspan=4)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        localip = self.find_local_ip()
        self.uri = "ws://{}/velocidrone".format(localip)
        if not localip: self.close()

        self.pl = PlayerList()
        self.pb = "-"
        self.deiconify()

    def load_splits(self, filename=None):
        if self.target_player.get() == "Enter player here":
            print("No player selected")
        else:
            json.dump({'target player':self.target_player.get()}, open(self.config_file_path, "w"))
            if not filename:
                #cd = os.path.dirname(os.path.realpath(__file__))
                file = filedialog.askopenfile("rb", initialdir=self.VDSplits_folder)
                self.open_file = file.name
                self.open_file_label.config(text=os.path.basename(file.name))
            else:
                file = open(filename, "rb")
            file_splits = pickle.load(file)
            self.pl.set_player_splits(self.target_player.get(), file_splits)
            self.pb = file_splits[[*file_splits.keys()][-1]]
            self.open_file_time.config(text=f"PB: {self.pb}s")
            self.split_label.config(text="-", fg='WHITE')

    def save_splits(self, filename=None):
        if self.target_player.get() == "Enter player here":
            print("No player selected")
        else:
            json.dump({'target player':self.target_player.get()}, open(self.config_file_path, "w"))
            if not filename:
                #cd = os.path.dirname(os.path.realpath(__file__))
                file = filedialog.asksaveasfile("wb", initialdir=self.VDSplits_folder)
                self.open_file = file.name
                self.open_file_label.config(text=os.path.basename(file.name))
            else:
                file = open(filename, "wb")
            pickle.dump(self.pl.get_player_splits(self.target_player.get()), file)
            self.save_splits_button.configure(bg='SystemButtonFace')
            #self.split_label.config(text="-", fg='WHITE')

    def clear_splits(self):
        self.pl.set_player_splits(self.target_player.get(), {})
        self.split_label.config(text="-", fg='WHITE')
        self.open_file = None
        self.open_file_label.config(text="Filename: NA")
        self.open_file_time.config(text="PB: -")
    
    #def auto_save_change(self):
    #    print(self.autosave.get())

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
                            return local_addr
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        return None

    def close(self):
        json.dump({'target player':self.target_player.get()}, open(self.config_file_path, "w"))
        for task in self.tasks:
            task.cancel()
        self.loop.stop()
        self.destroy()

loop = asyncio.get_event_loop()
app = App(loop)
loop.run_forever()
loop.close()