import re
import datetime as dt

# Define a regex pattern to match the datetime at the start of each line
datetime_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}')

# Open the messages.log file and read it line by line
with open('messages_original.log', 'r') as file:
    with open('messages.log', 'w') as new_file:
        last_time = None
        time_delta = None
        total_accrued_time = dt.timedelta()
        for line in file:
            stripped_line = line.strip()
            date_time_string = re.match(datetime_pattern, stripped_line).group()
            date_time_obj = dt.datetime.strptime(date_time_string, '%Y-%m-%d %H:%M:%S,%f')
            if last_time:
                time_delta = date_time_obj - last_time
            last_time = date_time_obj
            if time_delta:
                if time_delta.total_seconds() > 100:
                    print("Time delta greater than 1 second detected: {}".format(time_delta.total_seconds()))
                    total_accrued_time += time_delta - dt.timedelta(seconds=5)
                    shortened_date_time_obj = date_time_obj - total_accrued_time
                    print("proposed new time stamp: {}, total accrued time: {}".format(shortened_date_time_obj, total_accrued_time))
                ammended_date_time_obj = date_time_obj - total_accrued_time
                new_line = "{}{}".format(ammended_date_time_obj.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3], stripped_line[23:])
                print(new_line)
                new_file.write(new_line + '\n')