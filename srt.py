#!/usr/bin/env python

import sys
import getopt

VERSION="1.3"

class Timecode:
    def __init__(self, time):
        if isinstance(time, (int, long)):
            self.ms = time

        elif isinstance(time, str):
            if time[0] == '-':
                time = time[1:]
                sign = -1
            else:
                sign = 1

            length = len(time)
            if length == 12:
                hours, minutes, seconds = time.split(':')
            elif length == 9:
                minutes, seconds = time.split(':')
                hours = '0'
            elif length == 6:
                seconds = time
                hours, minutes = '0', '0'
            elif length == 5:
                minutes, seconds = time.split(':')
                seconds += ",000"
                hours = '0'
            elif length <= 3 and length > 0:
                seconds = "0," + time
                hours, minutes = '0', '0'
            else:
                raise InvalidTimestringException()
            seconds, milliseconds = seconds.split(',')

            self.ms = sum([
                int(seconds, 10) * 1000,
                int(minutes, 10) * 1000 * 60,
                int(hours, 10) * 1000 * 60 * 60,
                int(milliseconds, 10)
            ]) * sign

        else:
            raise InvalidTimeException()

    @staticmethod
    def stringify(total):
        """Return a properly-formatted SRT timecode given a number of milliseconds."""
        negative = False
        if total < 0:
            total = -total
            negative = True

        milliseconds = total % 1000
        total /= 1000

        seconds = total % 60
        total /= 60

        minutes = total % 60
        total /= 60

        hours = total

        sign = '-' if negative else ''
        return "%s%02d:%02d:%02d,%03d" % (sign, hours, minutes, seconds, milliseconds)

    def __str__(self):
        return self.stringify(self.ms)
    def __repr__(self):
        return 'Timecode("%s")' % str(self)
    def milliseconds(self):
        return self.ms

    def checktype(f):
        def check(self, other):
            if not isinstance(other, Timecode):
                raise TypeError()
            return f(self, other)

        return check

    @checktype
    def __add__(self, other): return Timecode(self.ms + other.ms)

    @checktype
    def __sub__(self, other): return Timecode(self.ms - other.ms)

    @checktype
    def __mul__(self, other): return Timecode(self.ms * other.ms)

    @checktype
    def __div__(self, other): return Timecode(self.ms / other.ms)

    def __pos__(self): return Timecode(self.ms)
    def __neg__(self): return Timecode(-self.ms)
    def __abs__(self): return Timecode(abs(self.ms))



class InvalidTimeException(Exception):
    def __init__(self):
        self.msg = "The time is not of accepted type."

    def __str__(self):
        return self.msg



class InvalidTimestringException(InvalidTimeException):
    def __init__(self):
        self.msg = "The timestring is not formatted correctly."

    def __str__(self):
        return self.msg



class SubRip(list):
    """A SubRip is a list consisting of dictionaries representing subtitles."""

    def __init__(self, rawdata):
        for each in rawdata.strip().replace('\r\n', '\n').split('\n\n'):
            each = each.split('\n')
            entry = {
                "index": int(each[0], 10),
                "text": "\n".join(each[2:])
            }
            start, end = [Timecode(p.strip()) for p in each[1].split("-->")]
            entry.update({"start": start, "end": end})

            self.append(entry)

    def __str__(self):
        return "\n\n".join([
            "%(index)s\n%(start)s --> %(end)s\n%(text)s" % each for each in self
        ])

    def shift_time_by(self, time):
        """Shift all timecodes by time, another timecode."""
        for each in self:
            each["start"] += time
            each["end"] += time

    def multiply_time_by(self, factor):
        """Multiply all timecodes by a float, rounding down."""
        for each in self:
            each["start"] = Timecode(int(each["start"].ms * factor))
            each["end"] = Timecode(int(each["end"].ms * factor))

    def shift_index_by(self, n):
        """Shift each index by n."""
        for each in self:
            each["index"] += n

    def resize(self, anchor, factor):
        """Resize (stretch or squeeze) by factor while leaving anchor untouched."""
        self.shift_time_by(-anchor)
        self.multiply_time_by(factor)
        self.shift_time_by(anchor)

    def reindex(self):
        """Rebuild index numbers sequentially, regardless of the original index numbers."""
        for i in range(0, len(self)):
            self[i]["index"] = i + 1



class SRT:
    @classmethod
    def aliases(self):
        return {
            "shift": self.shift,
            "shiftby": self.shiftby,
            "merge": self.merge,
            "reindex": self.reindex,
            "stretch": self.stretch, "squeeze": self.stretch,
            "sync": self.sync,
            "replace": self.replace,
            "version": self.version,
            "help": self.help, 'h': self.help, '?': self.help
        }

    @classmethod
    def help(self, argv):
        """usage: #{name} <subcommand> [args]

Available subcommands:
     merge
     shift
     shiftby
     reindex
     stretch (squeeze)
     sync
     replace
     version
     help (h, ?)
"""

        if len(argv) > 2:
            raise Usage(self.aliases()[argv[2]].__doc__)
        else:
            raise Usage(self.aliases()[argv[1]].__doc__)

    @classmethod
    def version(self, argv):
        """version: Display the version."""
        print "srt.py %s" % VERSION

    @classmethod
    def shiftby(self, argv):
        """shiftby: Shift all timecodes in subtitle file(s) by a certain duration.
usage: shiftby --by="TIMECODE" [FILES]...

Valid options:
    -b "TIMECODE" [--by="TIMECODE"] : The duration, specified in SRT timecode
                                      format, by which to shift subtitle file(s)"""

        opts, files = getopt.getopt(argv[2:], "b", ["by="])

        by = None
        for option, value in opts:
            if option == "--by":
                try:
                    by = Timecode(value)
                except:
                    raise Usage("Invalid duration to shift by.")

        if by == None:
            raise Usage("Duration to shift by must be specified.")

        for file in [open(file, "r+") for file in files]:
            subs = SubRip(file.read())
            subs.shift_time_by(by)
            try:
                file.seek(0)
                file.write(str(subs))
                file.truncate()
            finally:
                file.close()

    @classmethod
    def shift(self, argv):
        """shift: Shift all timecodes in subtitle file(s) by the difference between `to` and
       `target'.
usage: shift --target="TIMECODE" --to="TIMECODE" [FILES]...

Valid options:
    -a "TIMECODE" [--target="TIMECODE"] : The target timecode.
    -t "TIMECODE" [--to="TIMECODE"]     : The timecode to which the target is shifted."""

        opts, files = getopt.getopt(argv[2:], "at", ["target=", "to="])

        for option, value in opts:
            if option == "--target":
                try:
                    target = Timecode(value)
                except:
                    raise Usage("Invalid target timecode.")
            if option == "--to":
                try:
                    to = Timecode(value)
                except:
                    raise Usage("Invalid timecode to which the target is shifted.")

        if target == None:
            raise Usage("Target timecode must be specified.")
        if to == None:
            raise Usage("Timecode to which the target is shifted must be specified.")

        by = to - target

        for file in [open(file, "r+") for file in files]:
            subs = SubRip(file.read())
            subs.shift_time_by(by)
            try:
                file.seek(0)
                file.write(str(subs))
                file.truncate()
            finally:
                file.close()

    @classmethod
    def merge(self, argv):
        """merge: Merge all specified subtitle files according to the first file. Results
       are dumped to STDOUT.
usage: merge: BASEFILE SECONDFILE [OTHERFILES]..."""

        opts, files = getopt.getopt(argv[2:], "", [])

        if len(files) < 2:
            raise Usage("What good is there to merge, when there is naught but one item?")

        files = [open(file) for file in files]
        subs = [each.read() for each in files]
        for each in files:
            each.close()

        subs = [SubRip(each) for each in subs]
        base, subs = (subs[0], subs[1:])

        offset = base[-1]["end"]
        for sub in subs:
            sub.shift_time_by(offset)
            base.extend(sub)
            offset = sub[-1]["end"]
        base.reindex()

        print str(base)

    @classmethod
    def stretch(self, argv):
        """stretch: Stretch or squeeze all timecodes in subtitle file(s) by a certain
         factor.
usage: stretch --factor="FACTOR" [--anchor="TIMECODE"] [FILES]...

Valid options:
    -f "FACTOR" [--factor="FACTOR"]     : The factor by which to stretch or
                                          squeeze all timecodes in the subtitle
                                          file(s)
    -a "TIMECODE" [--anchor="TIMECODE"] : The anchor, or the timecode that will
                                          stay the same, specified in SRT timecode
                                          format. This is 00:00:00,000 by default."""

        opts, files = getopt.getopt(argv[2:], "fa", ["factor=", "anchor="])

        factor, anchor = None, None
        for option, value in opts:
            if option == "--factor":
                try:
                    factor = float(value)
                except:
                    raise Usage("Invalid factor to multiply by.")
            if option == "--anchor":
                try:
                    anchor = Timecode(value)
                except:
                    raise Usage("Invalid anchor to base on.")

        if factor == None:
            raise Usage("Factor to multiply by must be specified.")
        if anchor == None:
            anchor = Timecode("00:00:00,000")

        for file in [open(file, "r+") for file in files]:
            subs = SubRip(file.read())
            subs.resize(anchor, factor)
            try:
                file.seek(0)
                file.write(str(subs))
                file.truncate()
            finally:
                file.close()

    @classmethod
    def sync(self, argv):
        """sync: Make timecode `target' become timecode `goal' by intelligently stretching or
      squeezing with respect to the anchor.
usage: sync --target="TIMECODE" --goal="TIMECODE" [--anchor="TIMECODE"] [FILES]...

Valid options:
    -t "TIMECODE" [--target="TIMECODE"] : The source timecode.
    -g "TIMECODE" [--goal="TIMECODE"]   : The destination timecode.
    -a "TIMECODE" [--anchor="TIMECODE"] : The anchor, or the timecode that will
                                          stay the same, specified in SRT timecode
                                          format. This is 00:00:00,000 by default."""

        opts, files = getopt.getopt(argv[2:], "tga", ["target=", "goal=", "anchor="])

        target, goal, anchor = None, None, None
        for option, value in opts:
            if option == "--target":
                try:
                    target = Timecode(value)
                except:
                    raise Usage("Invalid timecode to target.")
            if option == "--goal":
                try:
                    goal = Timecode(value)
                except:
                    raise Usage("Invalid timecode as goal.")
            if option == "--anchor":
                try:
                    anchor = Timecode(value)
                except:
                    raise Usage("Invalid anchor to base on.")

        if target == None:
            raise Usage("A timecode to target must be specified.")
        if goal == None:
            raise Usage("A timecode as goal must be specified.")
        if anchor == None:
            anchor = Timecode("00:00:00,000")

        for file in [open(file, "r+") for file in files]:
            subs = SubRip(file.read())
            target -= anchor
            goal -= anchor
            factor = float(goal.milliseconds()) / float(target.milliseconds())
            subs.resize(anchor, factor)
            try:
                file.seek(0)
                file.write(str(subs))
                file.truncate()
            finally:
                file.close()

    @classmethod
    def reindex(self, argv):
        """reindex: Reindex all specified subtitle files, ignoring the original indices.
usage: reindex: FILES..."""

        opts, files = getopt.getopt(argv[2:], "", [])

        for file in [open(file, "r+") for file in files]:
            subs = SubRip(file.read())
            subs.reindex()
            try:
                file.seek(0)
                file.write(str(subs))
                file.truncate()
            finally:
                file.close()

    @classmethod
    def replace(self, argv):
        """replace: Replace a string with another string for all lines in the specified
         subtitle file(s).
usage: replace --find="STRING1" --replace-with="STRING2" [FILES]...

Valid options:
    -f "STRING1" [--find="STRING1"]         : The string to search for.
    -r "STRING2" [--replace-with="STRING2"] : The string to replace with."""

        opts, files = getopt.getopt(argv[2:], "fr", ["find=", "replace-with="])

        find, replace = None, None
        for option, value in opts:
            if option == "--find":
                find = value
            if option == "--replace-with":
                replace = value

        if find == None or replace == None:
            raise Usage("Both the string to search for and the string to replace with must be specified.")

        for file in [open(file, "r+") for file in files]:
            subs = SubRip(file.read())
            for sub in subs:
                sub["text"] = sub["text"].replace(find, replace)

            try:
                file.seek(0)
                file.write(str(subs))
                file.truncate()
            finally:
                file.close()



class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg



def main(argv=None):
    if argv is None:
        argv = sys.argv

    try:
        try:
            # No subcommand specified
            if len(argv) < 2:
                argv.append("help")

            subcommand = argv[1]
            # Strip away prefixing dashes in subcommands
            for t in (1, 2):
                if subcommand[0] == '-':
                    subcommand = subcommand[1:]

            if subcommand not in SRT.aliases():
                raise Usage("Unrecognized subcommand. \nType '#{name} help' for usage.")

            # Dispatch arguments
            SRT.aliases()[subcommand](argv)

        except getopt.error, msg:
            raise Usage(msg.msg)

    except Usage, err:
        name = sys.argv[0].split('/')[-1]
        print >> sys.stderr, str(err.msg.replace("#{name}", name))
        return 2

if __name__ == "__main__":
    sys.exit(main())

