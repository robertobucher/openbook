#!/usr/bin/env python


"""
wrapper to run lilypond.
run lilypond to produce the book
lilypond --ps --pdf --output=$(OUT_BASE) $(OUT_LY)

Why do we need this script?
- To make sure to remove the outputs (all of them - ps, pdf, ...) in any case of error.
- To get over lilypond printing junk on the console that I dont want to see when building.
- To get over the fact that lilypond does not have a "treat warnings as errors and stop" flag.
- To print the lilypond output, but only in case of error.
- To do extra stuff on the output coming out from lilypond like reduce the size of the pdf and more.
"""

import sys
import os
import os.path
import subprocess
import shutil
import tempfile

from pytconf import Config, ParamCreator, config_arg_parse_and_launch, register_endpoint, \
        register_main
from pytconf.extended_enum import ExtendedEnum


DESCRIPTION="Run the lilypond wrapper"
VERSION="1.0"
APP_NAME="lilypond wrapper"


def remove_outputs_if_exist() -> None:
    """
    remove the target files, do nothing if they are not there
    :return:
    """
    if os.path.isfile(ConfigAll.ps):
        os.unlink(ConfigAll.ps)
    if os.path.isfile(ConfigAll.pdf):
        os.unlink(ConfigAll.pdf)


def print_outputs(output: str, errout: str, status: int, args: list[str]) -> None:
    """
    print output of the program in case of error
    """
    if output != "":
        print(f"{sys.argv[0]}: stdout is", file=sys.stderr)
        print(output, file=sys.stderr)
    if errout != "":
        print(f"{sys.argv[0]}: stderr is", file=sys.stderr)
        print(errout, file=sys.stderr)
    print(f"{sys.argv[0]}: return code is [{status}]", file=sys.stderr)
    print(f"{sys.argv[0]}: error in executing {args}", file=sys.stderr)


def system_check_output(args: list[str]) -> None:
    """
    this function is here because we want to supress output until we know
    there is an error (and subprocess.check_output does not do this)
    """
    if ConfigAll.do_debug:
        print(f"{sys.argv[0]}: running [{args}]", file=sys.stderr)
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        (output, errout) = process.communicate()
        output = output.decode()
        errout = errout.decode()
        if ConfigAll.do_debug or process.returncode or \
            (ConfigAll.stop_on_output and (output != "" or errout != "")):
            print_outputs(output, errout, process.returncode, args)
            remove_outputs_if_exist()
            sys.exit(1)


class LilypondLogLevels(ExtendedEnum):
    """
    Class to enumerate the log levels of lilypond
    """
    NONE = 0
    ERROR = 1
    WARNING = 2
    BASIC = 3
    PROGRESS = 4
    INFO = 5  # this is the lilypond default
    DEBUG = 6


class ConfigAll(Config):  # pylint: disable=too-few-public-methods
    """
    All parameters for the run
    """
    do_ps = ParamCreator.create_bool(default=True, help_string="do postscript?")
    do_pdf = ParamCreator.create_bool(default=True, help_string="do pdf?")
    do_debug = ParamCreator.create_bool(default=False, help_string="emit debug info?")
    unlink_ps = ParamCreator.create_bool(
            default=False,
            help_string="unlink the postscript file at the end?",
    )
    do_qpdf = ParamCreator.create_bool(
            default=True,
            help_string="do you want to linearize the pdf file afterwards?",
    )
    # we should work with warnings and try and solve all of them
    loglevel = ParamCreator.create_enum(
        enum_type=LilypondLogLevels,
        # default=LilypondLogLevels.WARNING,
        default=LilypondLogLevels.ERROR,
        help_string="what warning level do you want?",
    )
    do_pdfred = ParamCreator.create_bool(
            default=False,
            help_string="should we reduce the pdf size?"
    )
    # this should be set to True
    stop_on_output = ParamCreator.create_bool(
        default=True,
        help_string="should we stop on any output from the lilypond process?",
    )

    # parameters without defaults (should be supplied by the user on the command line)
    ps = ParamCreator.create_new_file(help_string="postscript to produce")
    pdf = ParamCreator.create_new_file(help_string="pdf to produce")
    ly = ParamCreator.create_existing_file(help_string="lilypond input")

    output = ParamCreator.create_str(help_string="folder for outputs")


@register_endpoint(
    description="run the script",
    configs=[ConfigAll],
)
def run() -> None:
    """
    actually run this tool
    """
    if ConfigAll.do_debug:
        print(f"{sys.argv[0]}: arguments are [{sys.argv}]", file=sys.stderr)

    remove_outputs_if_exist()

    # run the command
    args = ["lilypond", f"--loglevel={ConfigAll.loglevel.name}"]
    if ConfigAll.do_ps:
        args.append("--ps")
    if ConfigAll.do_pdf:
        args.append("--pdf")
    args.append("--output=" + ConfigAll.output)
    args.append(ConfigAll.ly)
    try:
        # to make sure that lilypond shuts up...
        # subprocess.check_output(args)
        system_check_output(args)
        # chmod the results
        if ConfigAll.do_ps:
            os.chmod(ConfigAll.ps, 0o0444)
        if ConfigAll.do_pdf:
            os.chmod(ConfigAll.pdf, 0o0444)
    except OSError:
        remove_outputs_if_exist()
        print(f"{sys.argv[0]}: exiting because of errors", file=sys.stderr)
        sys.exit(1)

    # do pdf reduction
    if ConfigAll.do_pdfred:
        with tempfile.NamedTemporaryFile() as temp:
            # LanguageLevel=2 is the default
            system_check_output(["pdf2ps", "-dLanguageLevel=3", ConfigAll.pdf, temp.name])
            os.unlink(ConfigAll.pdf)
            system_check_output(["ps2pdf", temp.name, ConfigAll.pdf])

    # do linearization
    if ConfigAll.do_qpdf:
        # delete=False since we are going to move the file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            system_check_output(["qpdf", "--linearize", ConfigAll.pdf, temp.name])
            os.unlink(ConfigAll.pdf)
            shutil.move(temp.name, ConfigAll.pdf)

    # remove the postscript file if need be or chmod it
    if os.path.isfile(ConfigAll.ps):
        if ConfigAll.unlink_ps:
            os.unlink(ConfigAll.ps)
        else:
            os.chmod(ConfigAll.ps, 0o0444)

    # chmod the pdf file
    if os.path.isfile(ConfigAll.pdf):
        os.chmod(ConfigAll.pdf, 0o0444)


@register_main(
        app_name=APP_NAME,
        main_description=DESCRIPTION,
        version=VERSION,
)
def main() -> None:
    """ main entry point """
    config_arg_parse_and_launch()


if __name__ == "__main__":
    main()
