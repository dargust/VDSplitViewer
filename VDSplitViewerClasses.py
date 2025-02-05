import tkinter as tk

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
                    if not finished:
                        app.graph_frame.update_plot(uig, new_time, split)
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

class LivePlotWidget(tk.Canvas):
    def __init__(self, master=None, width=400, height=400, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.width = width
        self.height = height
        self.create_line(50, height - 50, width - 50, height - 50, arrow=tk.LAST)  # X-axis
        self.create_line(50, height - 50, 50, 50, arrow=tk.LAST)    # Y-axis

        self.splits = [[]]
        self.split_index = 0
        self.highest_gate = 0
        self.last_split_index = 0
        self.last_lap = 0

        self.colour_list = ["red","green","blue","magenta","yellow","cyan","purple", "pink"]
        self.current_colour_index = 0

    def update_plot(self, uig, time, split):
        if not split:
            return

        split_uig = uig.split("-")
        current_lap = int(split_uig[0])
        current_gate = int(split_uig[1])
        if current_gate > self.highest_gate:
            self.highest_gate = current_gate
        else:
            if not current_lap == self.last_lap:
                self.split_index += 1
            #self.highest_gate = 0
        self.delete("all")

        self.create_line(50, self.height - 50, self.width - 50, self.height - 50, arrow=tk.LAST)  # X-axis
        self.create_line(50, self.height - 50, 50, 50, arrow=tk.LAST)    # Y-axis
        
        multiplied_gate = current_gate + ((current_lap - 1) * self.highest_gate)
        if self.split_index == self.last_split_index or self.split_index == 0:
            self.splits[self.split_index] += [(current_gate,split)]
        else:
            self.splits.append([(current_gate,split)])
        
        total_min_x = 1.0e100
        total_max_x = -1.0e100
        total_min_y = 1.0e100
        total_max_y = -1.0e100
        # Find the min and max values for scaling
        for i in range(len(self.splits)):
            min_x = min(self.splits[i], key=lambda p: p[0])[0]
            max_x = max(self.splits[i], key=lambda p: p[0])[0]
            min_y = min(self.splits[i], key=lambda p: p[1])[1]
            max_y = max(self.splits[i], key=lambda p: p[1])[1]

            # Avoid division by zero
            if max_x == min_x:
                max_x += 1
            if max_y == min_y:
                max_y += 1
            if min_x < total_min_x:
                total_min_x = min_x
            if max_x > total_max_x:
                total_max_x = max_x
            if min_y < total_min_y:
                total_min_y = min_y
            if max_y > total_max_y:
                total_max_y = max_y

        #print("x min: {}, x max: {}, y min: {}, y max: {}".format(total_min_x, total_max_x, total_min_y, total_max_y))
        
        for i in range(len(self.splits)):
            self.current_colour_index = i % len(self.colour_list)
            temp_colour = self.colour_list[self.current_colour_index]
            points = self.splits[i]
            #print(points)

            # Scale points to fit within the canvas
            scaled_points = [
                (
                    50 + (x - total_min_x) / (total_max_x - total_min_x) * (self.width - 100),
                    self.height - 50 - (y - total_min_y) / (total_max_y - total_min_y) * (self.height - 100)
                )
                for x, y in points
            ]

            # Draw points
            for x, y in scaled_points:
                self.create_oval(x-2, y-2, x+2, y+2, fill=temp_colour)

            # Draw lines between points
            for i in range(len(scaled_points) - 1):
                x1, y1 = scaled_points[i]
                x2, y2 = scaled_points[i + 1]
                self.create_line(x1, y1, x2, y2, fill=temp_colour)

        # Draw axis labels and scales
        self.draw_x_axis_labels(total_min_x, total_max_x)
        self.draw_y_axis_labels(total_min_y, total_max_y)

        self.last_split_index = self.split_index
        self.last_lap = current_lap

    def draw_x_axis_labels(self, min_x, max_x):
        # Draw x-axis labels and scales with 2 decimal places and 4 evenly spaced labels
        step = (max_x - min_x) / 3
        for i in range(4):
            x_value = min_x + i * step
            x_position = 50 + i * (self.width - 100) / 3
            self.create_text(x_position, self.height - 30, text=f"{x_value:.2f}", anchor=tk.N)

    def draw_y_axis_labels(self, min_y, max_y):
        # Draw y-axis labels and scales with 2 decimal places and 4 evenly spaced labels
        step = (max_y - min_y) / 3
        for i in range(4):
            y_value = min_y + i * step
            y_position = self.height - 50 - i * (self.height - 100) / 3
            self.create_text(45, y_position, text=f"{y_value:.2f}", anchor=tk.E)

    def clear_plot(self):
        self.delete("all")
        self.splits = [[]]
        self.split_index = 0
        self.highest_gate = 0
        self.last_split_index = 0
        self.last_lap = 0
        self.current_colour_index = 0

def live_plot_test():
    root = tk.Tk()
    root.title("XY Graph")
    graph = LivePlotWidget(root)
    graph.pack()

    # Example points to plot
    graph.update_plot("1-1", 1.1, -0.2)

    root.mainloop()

if __name__ == "__main__":
    live_plot_test()