import socket

for line in open('snmp_dump.txt', encoding='utf-8'):
    if '=' not in line: continue
    oid, val = line.strip().split('=', 1)
    val = val.strip()
    try:
        vi = int(val)
        if 2450 <= vi <= 2465:
            print(f"BINGO (Exact int): {oid} = {vi}")
        if 245000 <= vi <= 246500:
            print(f"BINGO (dm2): {oid} = {vi}")
        if 26000 <= vi <= 27000:
            print(f"BINGO (sqft): {oid} = {vi}")
    except:
        pass
