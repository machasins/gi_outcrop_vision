import cv2
import glob
import time
import json
import gspread
import keyboard
import threading
import subprocess
import webbrowser
import numpy as np
import pyautogui as gui
import simpleaudio as sa
from os.path import isfile, abspath
from imgurpython import ImgurClient

from fast_match import FastImageFinderParallel as fifp

leyline_autofill_file_location = "../leyline_classify/run.bat"

region_offset = {
    "M" : 0,
    "L" : 1,
    "I" : 2,
    "S" : 3,
    "F" : 4,
    "N" : 5,
    "K" : 6,
}

region_name = {
    0 : "M",
    1 : "L",
    2 : "I",
    3 : "S",
    4 : "F",
    5 : "N",
    6 : "K",
}

url_region = 0
outcrop_screenshot_list = {}
leyline_screenshot_list = {}
outcrop_finders = []
leyline_finders = []

def clamp(n, minimum, maximum):
    return min(max(n, minimum), maximum)

def play(filename):
    sa.WaveObject.from_wave_file(filename).play()

def connect_to_imgur():
    if not isfile("imgur.json"):
        print("File \"imgur.json\" does not exist. Please create the file with your Imgur client credentials.")
        exit(1)
    client = None
    data = None
    with open("imgur.json" , 'r') as file:
        data = json.load(file)
        if "refresh_token" not in data.keys():
            client = ImgurClient(data["client_id"], data["client_secret"])
            auth_url = client.get_auth_url('pin')
            webbrowser.open_new_tab(auth_url)
            pin = input("Type given pin: ")
            credentials = client.authorize(pin, 'pin')
            client.set_user_auth(credentials['access_token'], credentials['refresh_token'])
        else:
            client = ImgurClient(data["client_id"], data["client_secret"], data["access_token"], data["refresh_token"])
    # Save refresh token
    data["access_token"] = client.auth.get_current_access_token()
    data["refresh_token"] = client.auth.get_refresh_token()
    with open("imgur.json", 'w') as file:
        json.dump(data, file)
    
    return client

def connect_to_sheets():
    if not isfile("key.json"):
        print("File \"key.json\" does not exist. Please create the file with your Google Sheets credentials.")
        exit(1)
    # Authenticate Google Sheets API
    client = gspread.service_account("key.json")
    try:
        ws = client.open_by_key(config["sheet_id"])
        return ws.worksheet("DataEntry")
    except:
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
    outcrop_results = []
    leyline_results = []
    threads = []
    for i, n in region_name.items():
        play("./sounds/" + n + ".wav")
        if i in outcrop_screenshot_list:
            for s in outcrop_screenshot_list[i]:
                outcrop_results.extend(outcrop_finders[i].find_matches(s))
        if i in leyline_screenshot_list:
            for s in leyline_screenshot_list[i]:
                leyline_results.extend(leyline_finders[i].find_matches(s))
        play("./shoot.wav")
        time.sleep(0.5)
    
    def update_outcrops(res):
        def update_sheet(row, col):
            done = False
            while not done:
                try:
                    sheet.update_cell(row, col, 1) if not sheet.cell(row, col).value else []
                    done = True
                except:
                    time.sleep(5)
        
        thread_pool = []
        
        for f in res:
            name = f.removeprefix("./outcrops\\")
            section_end = name.index("_")
            index = int("".join(filter(str.isdigit, name[section_end + 1:name.index(".")])))
            section = int(name[1:section_end:]) - 1
            region = name[0]
            row = (region_offset[region] + 1) * 3
            col = (sum(config[region][:section])) + index
            thread = threading.Thread(target=update_sheet, args=(row, col))
            thread.start()
            thread_pool.append(thread)
    
        for t in thread_pool:
            t.join()
            
    outcrop_thread = threading.Thread(target=update_outcrops, args=(outcrop_results,))
    outcrop_thread.start()
    threads.append(outcrop_thread)
    
    play("./click.wav")
    
    def update_leylines(res):
        def update_sheet(row, col, color):
            done = False
            while not done:
                try:
                    sheet.update_cell(row, col, color) if not sheet.cell(row, col).value else []
                    done = True
                except:
                    time.sleep(5)
        
        thread_pool = []
        
        for f in res:
            name = f.removeprefix("./leylines_specific\\")
            index = int("".join(filter(str.isdigit, name[:name.index(".")])))
            region = name[0]
            row = (region_offset[region] + 1) * 3
            col = config["leyline_offset"] + index
            color = name[1]
            thread = threading.Thread(target=update_sheet, args=(row, col, color))
            thread.start()
            thread_pool.append(thread)
    
        for t in thread_pool:
            t.join()
            
    leyline_thread = threading.Thread(target=update_leylines, args=(leyline_results,))
    leyline_thread.start()
    threads.append(leyline_thread)
    
    for t in threads:
        t.join()
    
    play("./success.wav")
    
    subprocess.run(abspath(leyline_autofill_file_location), cwd=abspath("../leyline_classify"))
            
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
client = connect_to_imgur()

play("./sounds/M.wav")

keyboard.add_hotkey('num 2', calc)
keyboard.add_hotkey('num 5', find_outcrops)
keyboard.add_hotkey('num 4', find_leylines)
keyboard.add_hotkey('num 6', switch_nation)
keyboard.wait('num 1') 