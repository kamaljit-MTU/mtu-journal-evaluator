import re

with open('Internshipt_Policy_Draft.md', 'r') as f:
    md_text = f.read()

def rtf_escape(text):
    text = text.replace('\\', '\\\\')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    text = text.replace('\n', '\\par ')
    return text

rtf = '{\\rtf1\\ansi\\deff0'
rtf += '{\\fonttbl{\\f0 Times New Roman;}}'
rtf += '\\paperw12240\\paperh15840\\margl1440\\margr1440\\margt1440\\margb1440'
rtf += '\\fs24 '

table = None

def flush_table():
    global table, rtf
    if table is not None:
        rtf += '}'
        table = None

for raw_line in md_text.split('\n'):
    line = raw_line.rstrip('\n')
    stripped = line.strip()
    if not stripped or stripped == '---':
        if stripped == '---':
            rtf += '\\line '
        else:
            rtf += '\\par '
        continue

    if line.startswith('# ') and 'MANIPUR' in line:
        continue
    elif line.startswith('## '):
        flush_table()
        text = rtf_escape(line[3:])
        rtf += '\\b\\fs28\\qc ' + text + '\\b0\\fs20\\par\\par '
    elif line.startswith('### '):
        flush_table()
        text = rtf_escape(line[4:])
        rtf += '\\b\\fs24 ' + text + '\\b0\\fs20\\par '
    elif line.startswith('- ') or line.startswith('* '):
        flush_table()
        text = rtf_escape(line[2:])
        rtf += '\\bullet ' + text + '\\par '
    elif line.startswith('| '):
        if '---' in line:
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if not cells:
            continue
        if table is None:
            flush_table()
            rtf += '\\trowd'
            for _ in cells:
                rtf += '\\cellx9000'
            rtf += '\\intbl '
            table = []
        row_text = ''
        for cell in cells:
            row_text += '\\intbl ' + rtf_escape(cell) + '\\cell '
        table.append(row_text)
    elif re.match(r'^\\d+\\.\\s', line):
        flush_table()
        text = rtf_escape(re.sub(r'^\\d+\\.\\s', '', line))
        rtf += '\\tab ' + text + '\\par '
    elif line.startswith('```'):
        continue
    else:
        flush_table()
        text = rtf_escape(line)
        rtf += text + '\\par '

flush_table()
rtf += '}'

with open('Internship_Policy_Draft.rtf', 'w') as f:
    f.write(rtf)

print('Saved Internship_Policy_Draft.rtf')
