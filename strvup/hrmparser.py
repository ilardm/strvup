import logging
import datetime


LOG = logging.getLogger('strvup.hrmparser')


class HrmParser:

    _PARSERS = {
        'Params': '_parse_params',
        'HRData': '_parse_hrm_data',
    }

    def __init__(self, path):
        self.path = path
        self.sections = {}

    @staticmethod
    def _parse_params(lines):
        data = {}
        for line in lines:
            key, value = line.split('=')
            pvalue = None

            if key == 'Date':
                pvalue = datetime.datetime.strptime(value, '%Y%m%d').date()
            elif key == 'StartTime':
                pvalue = datetime.datetime.strptime(value, '%H:%M:%S.%f').time()
            elif key == 'Interval':
                pvalue = int(value)

            if pvalue:
                data[key] = pvalue
        return data

    @staticmethod
    def _parse_hrm_data(lines):
        data = []
        for line in lines:
            # TODO: support cadence/speed/altitude/...
            values = line.split('\t')
            data.append(int(values[0]))

        return data

    def parse(self):
        c_section = ''

        with open(self.path, 'r') as ifd:
            for line in ifd:
                line = line.replace('\n', '')
                is_section = line.startswith('[') \
                             and line.endswith(']')

                if is_section:
                    c_section = line.replace('[', '').replace(']', '')
                    LOG.debug('started section %r', c_section)
                    self.sections[c_section] = []
                    continue

                is_empty = line == ''
                if is_empty:
                    LOG.debug('ended section %r', c_section)
                    c_section = ''
                    continue

                self.sections[c_section].append(line)

        LOG.debug('sctions: %r', self.sections.keys())

        for section, lines in self.sections.items():
            parser = self._PARSERS.get(section)
            if not parser:
                continue

            parser = getattr(self, parser)
            if not parser:
                continue

            LOG.debug('apply %r section parser', section)
            self.sections[section] = parser(lines)

        return self
