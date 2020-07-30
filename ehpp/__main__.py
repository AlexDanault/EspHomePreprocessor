# TODO change devies.yaml from arg to flag with default value

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import yaml

from colorama import init as init_colorama

from .consts import VERSION
from .utils import log, log_highlight, info, warn, error, deep_merge
from .yaml_utils import init_yaml, ordered_load, ordered_dump


class EspHomePreprocessorError(Exception):
    pass


class EspHomePreprocessorDeviceError(EspHomePreprocessorError):
    def __init__(self, file,  message):
        super(EspHomePreprocessorError, self).__init__(message)

        self.file = file
        self.message = message

    def __str__(self):
        return self.file + ":" + self.message


class EspHomePreprocessorTemplateError(EspHomePreprocessorError):
    def __init__(self, file, line, message):
        super(EspHomePreprocessorError, self).__init__(message)

        self.file = file
        self.line = line
        self.message = message

    def __str__(self):
        return self.file + ":" + str(self.line+1) + " " + self.message


def main():
    init_colorama()

    try:
        return run(sys.argv)
    except EspHomePreprocessorError as e:
        error(e)
        return 1
    except KeyboardInterrupt:
        return 1


def run(argv):
    args = parse_args(argv)

    if args.command == "version":
        return run_version(args)
    elif args.command == "build":
        return run_build(args)
    else:
        raise EspHomePreprocessorError(
            "Unknown command: {}".format(args.command))


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="ehpp")

    subparsers = parser.add_subparsers(help="Commands", dest="command")
    subparsers.required = True

    parser_version = subparsers.add_parser(
        "version", help="Get version number.")

    parser_build = subparsers.add_parser("build", help="Build output.")

    parser_build.add_argument(
        "filename", help="The YAML device file to build.")

    return parser.parse_args(argv[1:])


def run_version(args):
    print("EspHomePreprocessor version {}".format(VERSION))
    return 0


def run_build(args):
    init_yaml()

    log_highlight("Building device '{}'...".format(args.filename))

    hierarchy = []
    device = load_device(args.filename, hierarchy)

    fill_device_tags(device, device, args.filename)

    validate_device(device)

    log("Loading template file '{}'...".format(device['template']))
    template = load_template(device)

    output = process_template(template, device)

    save_output(output, device)

    return 0


def load_device(filename, hierarchy):
    log("Loading device file '{}'...".format(filename))

    try:
        with open(filename, "r") as stream:
            try:
                device = ordered_load(stream, yaml.SafeLoader)
            except yaml.YAMLError as ex:
                raise EspHomePreprocessorError(
                    "Error parsing device file: '{}'".format(ex))
    except IOError as ex:
        raise EspHomePreprocessorError(
            "Error loading device file: '{}'".format(ex))

    hierarchy.append(device)

    if 'inherits' in device:
        inherits = device["inherits"]
        del device["inherits"]

        for inherit in inherits:
            load_device(inherit, hierarchy)

    hierarchy.reverse()

    computed_device = dict()

    for device in hierarchy:
        if 'undefines' in device:
            undefines = device["undefines"]
            del device["undefines"]

            for undefine in undefines:
                if 'defines' in computed_device and undefine in computed_device["defines"]:
                    del computed_device["defines"][undefine]

        deep_merge(computed_device, device)

    computed_device["defines"]["id"] = os.path.splitext(filename)[0]

    return computed_device


def fill_device_tags(device, items, filename):
    for k, v in items.items():
        if isinstance(v, dict):
            fill_device_tags(device, v, filename)
        elif isinstance(v, list):
            for d in v:
                fill_device_tags(device, d, filename)
        elif isinstance(v, str):
            items[k] = replace_tags(device, v, 'device', filename)


def validate_device(device):
    if 'template' not in device:
        raise EspHomePreprocessorError("Device has no template")

    if 'output_directory' not in device:
        raise EspHomePreprocessorError("Device has no output directory")


def load_template(device):
    f = open(device["template"], "r")
    template = f.readlines()
    f.close()

    return template


def process_template(template, device):
    output = []
    ifblocks = []
    keep = True

    for linenumber, line in enumerate(template):
        ln = line.strip()

        if ln.startswith("#rem"):
            pass
        elif ln.startswith("#ifdef") or ln.startswith("#ifndef"):
            parts = ln.split()

            if len(parts) < 2:
                raise EspHomePreprocessorTemplateError(
                    device["template"], linenumber, "Template has directive '{}' but no identifier".format(parts[0]))

            keep = False
            joiner = ''
            while len(parts) >= 2:
                if parts[0] == "#ifdef" and (parts[1] in device["defines"]):
                    inner_keep = True
                elif parts[0] == "#ifndef" and (parts[1] not in device["defines"]):
                    inner_keep = True
                else:
                    inner_keep = False

                if joiner == '':
                    keep = inner_keep
                elif joiner == 'and':
                    keep = keep and inner_keep
                elif joiner == 'or':
                    keep = keep or inner_keep

                if len(parts) > 2:
                    if parts[2] == 'and':
                        joiner = 'and'
                        parts = parts[1:]
                    elif parts[2] == 'or':
                        joiner = 'or'
                        parts = parts[1:]
                    else:
                        raise EspHomePreprocessorTemplateError(
                            device["template"], linenumber, "Template has directive '{}' with unnwon modifier '{}'".format(parts[0], parts[1]))

                parts = parts[2:]

            ifblocks.append(keep)

            keep = calc_keep(ifblocks)
        elif ln.startswith("#else"):
            ifblocks[-1] = not ifblocks[-1]

            keep = calc_keep(ifblocks)
        elif ln.startswith("#endif"):
            if len(ifblocks) == 0:
                raise EspHomePreprocessorTemplateError(
                    device["template"], linenumber, "#endif nesting error, template tried closing block when none are open.")

            ifblocks.pop()

            keep = calc_keep(ifblocks)
        elif ln.startswith("#info"):
            if keep:
                parts = ln.split()
                info(" ".join(parts[1:]))
        elif ln.startswith("#warn"):
            if keep:
                parts = ln.split()
                warn(" ".join(parts[1:]))
        elif ln.startswith("#error"):
            if keep:
                parts = ln.split()
                raise EspHomePreprocessorTemplateError(
                    device["template"], linenumber, " ".join(parts[1:]))
        elif ln.startswith("#"):
            parts = ln.split()
            raise EspHomePreprocessorTemplateError(
                device["template"], linenumber, "Template has unknown directive '{}'".format(parts[0]))
        else:
            if keep:
                output.append(replace_tags(
                    device, line, 'template', None, linenumber))

    if len(ifblocks) != 0:
        raise EspHomePreprocessorTemplateError(
            device["template"], linenumber, "#ifdef or #ifndef nesting error, template processing finished with unclosed blocks.")

    return cleanup_template(output)


def replace_tags(device, line, file_type, filename=None, linenumber=None):
    ln = line.strip()
    vars = re.findall(r"{#([^}]+)}", line)

    for var in vars:
        full_var = var
        var_parts = var.split()
        var_default = None
        var_error = None
        var_drop = False

        if len(var_parts) > 1:
            var = var_parts[0]

            if var_parts[1].lower() == "or":
                if len(var_parts) > 2:

                    if var_parts[2].lower() == "default":
                        if len(var_parts) < 4:
                            replace_tags_error(
                                device, file_type, filename, linenumber, "has tag '{}' with 'or' modifier and 'default' instruction but no default value".format(var))
                            # raise EspHomePreprocessorTemplateError(
                            # device["template"], linenumber, "Template has tag '{}' with 'or' modifier and 'default' instruction but no default value".format(var))

                        var_default = " ".join(var_parts[3:])
                    elif var_parts[2].lower() == "error":
                        if len(var_parts) < 4:
                            replace_tags_error(
                                device, file_type, filename, linenumber, "has tag '{}' with 'or' modifier and 'error' instruction but no error message".format(var))

                        var_error = " ".join(var_parts[3:])
                    elif var_parts[2].lower() == "drop":
                        var_drop = True
                    else:
                        replace_tags_error(
                            device, file_type, filename, linenumber, "has tag '{}' with 'or' modifier but unknown instruction '{}'".format(var, var_parts[2]))

                else:
                    replace_tags_error(
                        device, file_type, filename, linenumber, "has tag '{}' with 'or' modifier but no instruction".format(var))
            else:
                replace_tags_error(
                    device, file_type, filename, linenumber, "has tag '{}' with unnwon modifier '{}'".format(var, var_parts[1]))

        if 'defines' in device and var in device["defines"]:
            value = device["defines"][var]
        else:
            if var_default is not None:
                value = var_default
            elif var_error is not None:
                replace_tags_error(
                    device, file_type, filename, linenumber, var_error)
            elif var_drop:
                value = None
            else:
                replace_tags_error(
                    device, file_type, filename, linenumber, "expects a define named '{}' but device didn't define it".format(var))

        tag = "{#"+full_var+"}"
        pos = line.index(tag)

        if value is None:
            line = ""
        else:
            if type(value) is str:
                pass

            elif type(value) is int:
                value = str(value)

            elif type(value) in [list, tuple]:
                value = ordered_dump(
                    value, default_flow_style=False)

            # if tag was alone, we must indent it properly
            if ln == tag:
                line = ""
                for value_line in value.splitlines():
                    line += " "*pos + value_line + "\n"
            else:
                line = line.replace(tag, value)

    return line.rstrip()


def replace_tags_error(device, type, filename, linenumber, msg):
    if type == 'device':
        raise EspHomePreprocessorDeviceError(
            filename, "Device {}".format(msg))
    elif type == 'template':
        raise EspHomePreprocessorTemplateError(
            device["template"], linenumber, "Template {}".format(msg))


def cleanup_template(output):
    # Remove all consecutive newlines
    deletes = []
    prevline = ""
    for linenumber, line in enumerate(output):
        line = line.strip()
        if (prevline == "" and line == ""):
            deletes.append(linenumber)

        prevline = line

    for delete in reversed(deletes):
        del output[delete]

    return output


def calc_keep(ifblocks):
    for ifblock in ifblocks:
        if not ifblock:
            return False

    return True


def save_output(output, device):
    directory = device["output_directory"]

    if not os.path.isdir(directory):
        raise EspHomePreprocessorError(
            "Output directory '{0}' does not exist.".format(directory))

    if 'output_filename' in device:
        filename = directory + os.path.sep + device["output_filename"]
    else:
        filename = directory + os.path.sep + device["defines"]["id"] + ".yaml"

    log("Writing output to file '{}'...".format(filename))

    with open(filename, 'w') as f:
        for line in output:
            f.write("%s\n" % line)

    log_highlight("Done!")


if __name__ == "__main__":
    sys.exit(main())
