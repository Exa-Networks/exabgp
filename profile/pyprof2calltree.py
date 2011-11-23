#!/usr/bin/env python

# Copyright (c) 2006-2008, David Allouche, Jp Calderone, Itamar Shtull-Trauring,
# Johan Dahlin, Olivier Grisel <olivier.grisel@ensta.org>
#
# All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""pyprof2calltree: profiling output which is readable by kcachegrind

This script can either take raw cProfile.Profile.getstats() log entries or
take a previously recorded instance of the pstats.Stats class.
"""

import cProfile
import pstats
import optparse
import os
import sys
import tempfile

__all__ = ['convert', 'visualize', 'CalltreeConverter']

class Code(object):
    pass

class Entry(object):
    pass

def pstats2entries(data):
    """Helper to convert serialized pstats back to a list of raw entries

    Converse opperation of cProfile.Profile.snapshot_stats()
    """
    entries = dict()
    allcallers = dict()

    # first pass over stats to build the list of entry instances
    for code_info, call_info in data.stats.items():
        # build a fake code object
        code = Code()
        code.co_filename, code.co_firstlineno, code.co_name = code_info

        # build a fake entry object
        cc, nc, tt, ct, callers = call_info
        entry = Entry()
        entry.code = code
        entry.callcount = cc
        entry.reccallcount = nc - cc
        entry.inlinetime = tt
        entry.totaltime = ct

        # to be filled during the second pass over stats
        entry.calls = list()

        # collect the new entry
        entries[code_info] = entry
        allcallers[code_info] = callers.items()

    # second pass of stats to plug callees into callers
    for entry in entries.itervalues():
        entry_label = cProfile.label(entry.code)
        entry_callers = allcallers.get(entry_label, [])
        for entry_caller, call_info in entry_callers:
            entries[entry_caller].calls.append((entry, call_info))

    return entries.values()

class CalltreeConverter(object):
    """Convert raw cProfile or pstats data to the calltree format"""

    kcachegrind_command = "kcachegrind %s"

    def __init__(self, profiling_data):
        if isinstance(profiling_data, basestring):
            # treat profiling_data as a filename of pstats serialized data
            self.entries = pstats2entries(pstats.Stats(profiling_data))
        elif isinstance(profiling_data, pstats.Stats):
            # convert pstats data to cProfile list of entries
            self.entries = pstats2entries(profiling_data)
        else:
            # assume this are direct cProfile entries
            self.entries = profiling_data
        self.out_file = None

    def output(self, out_file):
        """Write the converted entries to out_file"""
        self.out_file = out_file
        print >> out_file, 'events: Ticks'
        self._print_summary()
        for entry in self.entries:
            self._entry(entry)

    def visualize(self):
        """Launch kcachegrind on the converted entries

        kcachegrind must be present in the system path
        """

        if self.out_file is None:
            _, outfile = tempfile.mkstemp(".log", "pyprof2calltree")
            f = file(outfile, "wb")
            self.output(f)
            use_temp_file = True
        else:
            use_temp_file = False

        try:
            os.system(self.kcachegrind_command % self.out_file.name)
        finally:
            # clean the temporary file
            if use_temp_file:
                f.close()
                os.remove(outfile)
                self.out_file = None

    def _print_summary(self):
        max_cost = 0
        for entry in self.entries:
            totaltime = int(entry.totaltime * 1000)
            max_cost = max(max_cost, totaltime)
        print >> self.out_file, 'summary: %d' % (max_cost,)

    def _entry(self, entry):
        out_file = self.out_file

        code = entry.code
        #print >> out_file, 'ob=%s' % (code.co_filename,)

        co_filename, co_firstlineno, co_name = cProfile.label(code)
        print >> out_file, 'fi=%s' % (co_filename,)
        print >> out_file, 'fn=%s %s:%d' % (
            co_name, co_filename, co_firstlineno)

        inlinetime = int(entry.inlinetime * 1000)
        if isinstance(code, str):
            print >> out_file, '0 ', inlinetime
        else:
            print >> out_file, '%d %d' % (code.co_firstlineno, inlinetime)

        # recursive calls are counted in entry.calls
        if entry.calls:
            calls = entry.calls
        else:
            calls = []

        if isinstance(code, str):
            lineno = 0
        else:
            lineno = code.co_firstlineno

        for subentry, call_info in calls:
            self._subentry(lineno, subentry, call_info)
        print >> out_file

    def _subentry(self, lineno, subentry, call_info):
        out_file = self.out_file
        code = subentry.code
        #print >> out_file, 'cob=%s' % (code.co_filename,)
        co_filename, co_firstlineno, co_name = cProfile.label(code)
        print >> out_file, 'cfn=%s %s:%d' % (
            co_name, co_filename, co_firstlineno)
        print >> out_file, 'cfi=%s' % (co_filename,)
        print >> out_file, 'calls=%d %d' % (call_info[0], co_firstlineno)

        totaltime = int(call_info[3] * 1000)
        print >> out_file, '%d %d' % (lineno, totaltime)

def main():
    """Execute the converter using parameters provided on the command line"""

    usage = "%s [-k] [-o output_file_path] [-i input_file_path] [-r scriptfile [args]]"
    parser = optparse.OptionParser(usage=usage % sys.argv[0])
    parser.allow_interspersed_args = False
    parser.add_option('-o', '--outfile', dest="outfile",
                      help="Save calltree stats to <outfile>", default=None)
    parser.add_option('-i', '--infile', dest="infile",
                      help="Read python stats from <infile>", default=None)
    parser.add_option('-r', '--run-script', dest="script",
                      help="Name of the python script to run to collect"
                      " profiling data", default=None)
    parser.add_option('-k', '--kcachegrind', dest="kcachegrind",
                      help="Run the kcachegrind tool on the converted data",
                      action="store_true")
    options, args = parser.parse_args()


    outfile = options.outfile

    if options.script is not None:
        # collect profiling data by running the given script

        sys.argv[:] = [options.script] + args
        if not options.outfile:
            outfile = '%s.log' % os.path.basename(options.script)

        prof = cProfile.Profile()
        try:
            try:
                prof = prof.run('execfile(%r)' % (sys.argv[0],))
            except SystemExit:
                pass
        finally:
            kg = CalltreeConverter(prof.getstats())

    elif options.infile is not None:
        # use the profiling data from some input file
        if not options.outfile:
            outfile = '%s.log' % os.path.basename(options.infile)

        if options.infile == outfile:
            # prevent name collisions by appending another extension
            outfile += ".log"

        kg = CalltreeConverter(pstats.Stats(options.infile))

    else:
        # at least an input file or a script to run is required
        parser.print_usage()
        sys.exit(2)

    if options.outfile is not None or not options.kcachegrind:
        # user either explicitely required output file or requested by not
        # explicitely asking to launch kcachegrind
        print "writing converted data to: " + outfile
        kg.output(file(outfile, 'wb'))

    if options.kcachegrind:
        print "launching kcachegrind"
        kg.visualize()


def visualize(profiling_data):
    """launch the kcachegrind on `profiling_data`

    `profiling_data` can either be:
        - a pstats.Stats instance
        - the filename of a pstats.Stats dump
        - the result of a call to cProfile.Profile.getstats()
    """
    converter = CalltreeConverter(profiling_data)
    converter.visualize()

def convert(profiling_data, outputfile):
    """convert `profiling_data` to calltree format and dump it to `outputfile`

    `profiling_data` can either be:
        - a pstats.Stats instance
        - the filename of a pstats.Stats dump
        - the result of a call to cProfile.Profile.getstats()

    `outputfile` can either be:
        - a file() instance open in write mode
        - a filename
    """
    converter = CalltreeConverter(profiling_data)
    if isinstance(outputfile, basestring):
        f = file(outputfile, "wb")
        try:
            converter.output(f)
        finally:
            f.close()
    else:
        converter.output(outputfile)


if __name__ == '__main__':
    sys.exit(main())
