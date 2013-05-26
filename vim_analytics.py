#!/usr/bin/env python2
import argparse
import os
import subprocess
import tempfile
from collections import defaultdict
from contextlib import contextmanager

DEFAULT_ADDONS_DIR = os.path.expanduser('~/.vim/addons')
VIM = 'vim'

def process_run(lines):
    '''
    Get timings for an individual run
    '''
    results = []
    for line in lines:
        try:
            time, elapsed, action = filter(lambda x: x, line.split(' ', 3))
            if elapsed.endswith(':'):
                elapsed = elapsed[:-1]
            time = float(time)
            elapsed = float(elapsed)
        except:
            # not a valid timing
            continue

        try:
            extra_time, actual_action = action.split(':', 1)
            float(extra_time)
            action = actual_action
        except:
            pass

        results.append((time, elapsed, action.strip()))

    return results


def process_log(filename='vim-startuptime.log'):
    '''
    Returns list of actions and total time spent processing them.
    '''
    results = defaultdict(lambda: defaultdict(list))

    with open(filename) as file:
        lines = file.readlines()

    # find runs
    runs = [idx for idx, line in enumerate(lines) if 'VIM STARTING' in line]

    # add run results
    for start, end in zip(runs, runs[1:]+[len(lines)]):
        for time, elapsed, action in process_run(lines[start:end]):
            results[action]['time'].append(time)
            results[action]['elapsed'].append(elapsed)

    # calculate averages
    for action in results:
        for k,v in results[action].items():
            avg = sum(v)/len(v)
            results[action][k] = {'times': v, 'average': avg}

    # get total time and return results without VIM messages
    total_time = results['--- VIM STARTED ---']['time']['average']
    return {k:v for k,v in results.iteritems() if not k.startswith('--- VIM')}, total_time


def group_by_addon(results, addons_dir=DEFAULT_ADDONS_DIR):
    '''
    Tries to group results by addon/bundle and derive a total.
    '''
    addons_dir = addons_dir.rstrip('/') + '/'
    addons = defaultdict(lambda: defaultdict(list))
    for action, averages in results.items():
        prefix = 'sourcing %s' % addons_dir
        if action.startswith(prefix):
            sourced_file = action[len(prefix):]
            addon = sourced_file.split(os.path.sep, 1)[0]
            addons[addon]['averages'].append(averages['elapsed']['average'])
            addons[addon]['files'].append((sourced_file[len(addon)+1:], averages['elapsed']['average']))

    # sum averages to find total time per addon
    for addon in addons:
        addons[addon]['total_average'] = sum(addons[addon]['averages'])
    return addons


@contextmanager
def run_vim(times, cmd=None, log_file=None):
    '''
    Runs vim specified number of times saving startuptime log to temporary file and returnings results of those runs.
    '''
    if not log_file:
        fd, log_file = tempfile.mkstemp()

    if not cmd:
        cmd = []
    else:
        cmd = cmd.split()

    cmd.insert(0, VIM)
    cmd.append('--startuptime')
    cmd.append(log_file)

    for i in xrange(times):
        subprocess.call(cmd)
    yield log_file

    # clean up if we created a temporary file
    if not log_file:
        os.remove(log_file)


def print_results(results, total_time, addons_dir=DEFAULT_ADDONS_DIR):
    '''
    Prints sorted results.
    '''
    print 'total     action'
    for action, averages in sorted(results.items(), key=lambda x: x[1]['elapsed']['average']):
        print '%07.3f - %s' % (averages['elapsed']['average'], action)
    print

    for addon, averages in sorted(group_by_addon(results, addons_dir).items(), key=lambda x: x[1]['total_average']):
        print addon
        for file, average in sorted(averages['files'], key=lambda x: x[1]):
            print '%07.3f - %s' % (average, file)
        print '%07.3f total' % averages['total_average']
        print

    print '%07.3f total' % total_time


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="A tool for analyzing vim's startup time",
        epilog="...lies, damned lies and statistics."
    )
    parser.add_argument('-a', '--addons-dir', action='store', nargs=1, default=DEFAULT_ADDONS_DIR, help='Location of your addons/bundle dir so we can group results properly')
    parser.add_argument('-c', '--cmd', action='store', help='Command to run vim with')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug results (drops you into ipdb)')
    parser.add_argument('-l', '--log', action='store', nargs=1, help='Log file to analyze')
    parser.add_argument('-r', '--runs', action='store', type=int, default=1, nargs=1, help='Number of runs to make before averaging them')
    parser.add_argument('-s', '--save', action='store', required=False, help='Save results to a file instead of printing them')

    args = parser.parse_args()

    if args.log:
        results, total_time = process_log(args.log)
    else:
        with run_vim(args.runs, args.cmd) as log:
            results, total_time = process_log(log)

    if args.save:
        import sys
        stdout = sys.stdout
        sys.stdout = open(args.save, 'w')
        print_results(results, total_time, addons_dir=args.addons_dir)
        sys.stdout = stdout
    else:
        print_results(results, total_time, addons_dir=args.addons_dir)

    if args.debug:
        import ipdb
        ipdb.set_trace()
