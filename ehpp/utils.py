from collections import Mapping

from colorama import Fore, Style

def log(msg):
  print("{}{}".format(Style.RESET_ALL, msg))

def log_highlight(msg):
  print("{}{}".format(Fore.GREEN, msg))

def info(msg):
  print("{}[INFO] {}".format(Fore.CYAN, msg))

def warn(msg):
  print("{}[WARN] {}".format(Fore.YELLOW, msg))

def error(msg):
  print("{}[ERROR] {}".format(Fore.RED, msg))

def deep_merge(dct, merge_dct):
  for k, v in merge_dct.items():
    if (k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], Mapping)):
      deep_merge(dct[k], merge_dct[k])
    else:
        dct[k] = merge_dct[k]