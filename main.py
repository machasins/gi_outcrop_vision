import glob
import time
import json
import gspread
import keyboard
import subprocess
import numpy as np
import pyautogui as gui
from os.path import isfile, abspath
from playsound3 import playsound as ps
from gspread.utils import rowcol_to_a1 as a1
from gspread.utils import ValueRenderOption, ValueInputOption

from fast_match import FastImageFinderParallel as fifp

region_offset = {
    "M" : 0,
    "L" : 1,
    "I" : 2,
    "S" : 3,
    "F" : 4,
    "N" : 5,
    "K" : 6,
    "Z" : 7,
}

region_name = {
    0 : "M",
    1 : "L",
    2 : "I",
    3 : "S",
    4 : "F",
    5 : "N",
    6 : "K",
    7 : "Z",
}

url_region: int = 0
outcrop_screenshot_list: dict[int, ] = {}
leyline_screenshot_list: dict[int, ] = {}
outcrop_finders: list[fifp] = []
leyline_finders: list[fifp] = []

def clamp(n:float, minimum:float, maximum:float):
    return min(max(n, minimum), maximum)

def play(filename:str):
    ps(filename, block=False)

def connect_to_sheets():
    if not isfile("key.json"):
        print("File \"key.json\" does not exist. Please create the file with your Google Sheets credentials.")
        exit(1)
    # Authenticate Google Sheets API
    client = gspread.service_account("key.json")
    for i in range(5):
        try:
            ws = client.open_by_key(config["sheet_id"])
            return ws.worksheet("DataEntry")
        except:
            print(f"[{ i }] There are issues with retrieving the sheet, please wait...")
            time.sleep(5)
    print("The sheet ID in the config is not valid with your account.")
    exit(1)

def setup_outcrop_finders():
    for n in region_offset.keys():
        outcrop_finders.append(fifp(glob.glob("./outcrops/" + n + "*.png"), threshold=0.915))

def setup_leyline_finders():
    for n in region_offset.keys():
        leyline_finders.append(fifp(glob.glob("./leylines_specific/" + n + "*.png"), threshold=0.9))

def read_config():
    with open("config.json") as file:
        config = json.load(file)
        return config

def switch_nation():
    global url_region
    url_region = (url_region + 1) % (max(region_offset.values()) + 1)
    play("./sounds/" + region_name[url_region] + ".wav")

def calc():
    outcrop_results: list[str] = []
    leyline_results: list[str] = []
    for i, n in region_name.items():
        if i in outcrop_screenshot_list or i in leyline_screenshot_list:
            play("./sounds/" + n + ".wav")
        if i in outcrop_screenshot_list:
            for s in outcrop_screenshot_list[i]:
                outcrop_results.extend(outcrop_finders[i].find_matches(s))
        if i in leyline_screenshot_list:
            for s in leyline_screenshot_list[i]:
                leyline_results.extend(leyline_finders[i].find_matches(s))
                
    play("./shoot.wav")
    
    updates: dict[tuple[int, int], (str, int)] = {}
    
    for f in outcrop_results:
        name = f.removeprefix("./outcrops\\")
        section_end = name.index("_")
        index = int("".join(filter(str.isdigit, name[section_end + 1:name.index(".")])))
        section = int(name[1:section_end:]) - 1
        region = name[0]
        row = (region_offset[region] + 1) * 3
        col = (sum(config[region][:section])) + index
        updates[(row, col)] = "1"
        
    for f in leyline_results:
        name = f.removeprefix("./leylines_specific\\")
        index = int("".join(filter(str.isdigit, name[:name.index(".")])))
        region = name[0]
        row = (region_offset[region] + 1) * 3
        col = config["leyline_offset"] + index
        color = name[1]
        updates[(row, col)] = color
    
    unique_rows = list(set([r for r, _ in updates.keys()]))
    max_col = max([coord[1] for coord in updates.keys()])
    
    ranges = [f"{ a1(r, 1) }:{ a1(r, max_col) }" for r in unique_rows]
    data: list[gspread.ValueRange] = sheet.batch_get(ranges, value_render_option=ValueRenderOption.unformatted)
    for (r, c), value in updates.items():
        if not data[unique_rows.index(r)] or not data[unique_rows.index(r)][0]:
            data[unique_rows.index(r)] = [[]]
        if len(data[unique_rows.index(r)][0]) < max_col:
            data[unique_rows.index(r)][0].extend([None]*(max_col - len(data[unique_rows.index(r)][0])))
            data[unique_rows.index(r)][0] = [None if d == "" else d for d in data[unique_rows.index(r)][0]]
        if data[unique_rows.index(r)][0][c - 1] is None:
            data[unique_rows.index(r)][0][c - 1] = value
    sheet.batch_update([{ "range" : r, "values" : data[i] } for i, r in enumerate(ranges)], value_input_option=ValueInputOption.user_entered)
    
    play("./success.wav")
    
    subprocess.run(abspath(config["leyline_autofill_file_location"]), cwd=abspath(config["leyline_autofill_file_location"] + "/.."))
            
def find_outcrops():
    global url_region
    if not url_region in outcrop_screenshot_list:
        outcrop_screenshot_list[url_region] = []
    outcrop_screenshot_list[url_region].append(gui.screenshot())
    play("./shoot.wav")

def find_leylines():
    global url_region
    if not url_region in leyline_screenshot_list:
        leyline_screenshot_list[url_region] = []
    leyline_screenshot_list[url_region].append(gui.screenshot())
    play("./shoot.wav")

config = read_config()
setup_outcrop_finders()
setup_leyline_finders()
sheet = connect_to_sheets()

play("./sounds/M.wav")

keyboard.add_hotkey('num 2', calc)
keyboard.add_hotkey('num 5', find_outcrops)
keyboard.add_hotkey('num 4', find_leylines)
keyboard.add_hotkey('num 6', switch_nation)
keyboard.wait('num 9') 