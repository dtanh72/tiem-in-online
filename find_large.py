for line in open('snmp_dump.txt', encoding='utf-8'):
    if '=' not in line: continue
    oid, val = line.strip().split('=', 1)
    val = val.strip()
    try:
        vi = int(val)
        if 2000000 <= vi <= 30000000 or 20000 <= vi <= 300000:
            print(f"{vi}: {oid}")
    except:
        pass
