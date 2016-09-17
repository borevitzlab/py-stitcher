from slacker import Slacker
import datetime
import os
import subprocess
import sys
import time
import csv
import traceback

with open('slack_api_key', 'r') as f:
    api_key = f.read().strip()
slack = Slacker(api_key)
response = slack.api.test();
if not response.body[u'ok']:
    raise("Slack API issue")
last_success = ""


def notify(msg):
    slack.chat.post_message('#stitcher-status', msg,
                            as_user=True, username="Botty McBotFace")


def urgent(msg):
    slack.chat.post_message('@jackadamson', msg,
                            as_user=True, username="Botty McBotFace")


def stitcher_path():
    """Return the path to the stitcher to call."""
    path = ''
    if sys.platform == 'darwin':
        path = "/Applications/GigaPan 2.3.0306/GigaPan Stitch 2.3.0306.app/Contents/MacOS/GigaPan Stitch 2.3.0306"
    if sys.platform == 'win32':
        path = '"\Program Files (x86)\GigaPan\GigaPan 2.1.0161\stitch.exe"'
    if os.path.isfile(path):
        return path
    raise RuntimeError("Stitcher not found")


def stitcher(image_path, n_rows, save_name):
    """
    Example use:
    stitcher("/home/user/julyimages",16,"/home/user/stitchedimages/july")
    Would create a panorama of all jpg's in julyimages and save a july.gigapan and july.tiff file in stitched images
    """

    images = os.listdir(image_path)
    images = [i for i in images if ".jpg" in i]
    imagepaths = [os.path.join(image_path, i) for i in images]
    imgsave = save_name + ".tiff"
    gigapansave = save_name + ".gigapan"
    with open(os.path.join(image_path, "imagelist.txt"), 'w') as imagelist:
        for i in imagepaths:
            imagelist.write(i + "\n")
        print("Wrote imagelist to " + os.path.join(image_path, "imagelist.txt"))
    stitch_args = [stitcher_path(), '--batch-mode', '--export-quit', '--stitch', '--title', "Panorama",
                   '--images'] + imagepaths + ['--downward', '--rightward', '--nrows', n_rows, '--save-as', gigapansave,
                                               "--export", "TIFF", "0", imgsave]
    p = subprocess.Popen(stitch_args)
    start = time.time()
    finish = start + 12000
    while p.poll() is None:
        time.sleep(0.5)
        if time.time() > finish:
            print("Image stitching timed out on folder " + image_path)
            return False
    return True


def stitch_hour(path, n_rows, save_directory, name, year, month, day, hour, start, end):
    date = datetime.datetime(int(year), int(month), int(day), int(hour))
    if start < date < end:
        if date.hour == 12:
            save_path = os.path.join(save_directory,
                                     "_".join([name, year, month, day, hour, "00", "00", "00"]))
            if stitcher(path, n_rows, save_path):
                notify("Success for {}: {}/{}/{} {}:00".format(name, day, month, year, hour))
                global last_success
                last_success = "{}/{}/{} {}:00".format(day, month, year, hour)
            else:
                notify("Failure for {}: {}/{}/{} {}:00".format(name, day, month, year, hour))


def stitch_day(path, n_rows, save_directory, name, year, month, day, start, end):
    for hour in get_rel_subdirectories(path):
        if hour.split("_")[-1].isdigit() and len(hour.split("_")) == 4:
            stitch_hour(os.path.join(path, hour), n_rows, os.path.join(save_directory, hour), name, year, month, day,
                        hour.split("_")[-1], start, end)


def stitch_month(path, n_rows, save_directory, name, year, month, start, end):
    for day in get_rel_subdirectories(path):
        if day.split("_")[-1].isdigit() and len(day.split("_")) == 3:
            stitch_day(os.path.join(path, day), n_rows, os.path.join(save_directory, day), name, year, month,
                       day.split("_")[-1], start, end)


def stitch_year(path, n_rows, save_directory, name, year, start, end):
    for month in get_rel_subdirectories(path):
        if month.split("_")[-1].isdigit() and len(month.split("_")) == 2:
            stitch_month(os.path.join(path, month), n_rows, os.path.join(save_directory, month), name, year,
                         month.split("_")[-1], start, end)


def stitch_stream(path, n_rows, save_directory, name, start=datetime.datetime.min, end=datetime.datetime.max):
    if not (n_rows is str):
        n_rows = str(n_rows)
    notify("Stitch started!\nRows: {}\nSource: {}\nSave: {}\nStart: {}\nEnd: {}".format(n_rows, path, save_directory,
                                                                                        start, end))
    try:
        for year in get_rel_subdirectories(path):
            if year.isdigit():
                stitch_year(os.path.join(path, year), n_rows, os.path.join(save_directory, year), name, year, start, end)
    except:
        print("Unexpected error!")
        print(sys.exc_info()[0])
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)

        notify("AN ERROR HAS OCCURRED!\n"+str(sys.exc_info()[0]))
        urgent("AN ERROR HAS OCCURRED!\n"+str(sys.exc_info()[0]))


def stitch_directory(path, depth, n_rows, save_directory):
    to_stitch = directories_at_depth(path, depth)
    print("Preparing to stitch " + str(len(to_stitch)) + " panoramas")
    current_image = 0
    with open('eggs.csv', 'w', newline='') as csvfile:
        data_writer = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for panorama in to_stitch:
            current_image += 1
            print("Stitching image " + str(current_image) + " of " + str(len(to_stitch)))
            if stitcher(panorama, n_rows, os.path.join(save_directory, panorama)):
                data_writer.writerow([panorama, "Success"])
            else:
                data_writer.writerow([panorama, "Failed"])


def directories_at_depth(path, depth):
    if depth > 0:
        dirs = []
        for directory in get_immediate_subdirectories(path):
            dirs = dirs + directories_at_depth(os.path.join(path, directory), depth - 1)
        return dirs
    return get_immediate_subdirectories(path)


def get_rel_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]


def get_immediate_subdirectories(a_dir):
    return [os.path.join(a_dir, name) for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]
