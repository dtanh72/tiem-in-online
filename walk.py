import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

async def walk_hp():
    tran = await UdpTransportTarget.create(('192.168.1.150', 161), timeout=2.0, retries=2)
    
    iterator = walk_cmd(
        SnmpEngine(),
        CommunityData('public', mpModel=0),
        tran,
        ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.4.1.11.2'))
    )
    
    with open('snmp_dump.txt', 'w') as f:
        pass
        
    print("Start walk...")
    count = 0
    try:
        async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if errorIndication:
                print(f"ErrInd: {errorIndication}")
                break
            elif errorStatus:
                print(f"ErrStat: {errorStatus}")
                break
            else:
                for varBind in varBinds:
                    count += 1
                    oid = varBind[0].prettyPrint()
                    val = varBind[1].prettyPrint()
                    
                    if '245' in val or '264' in val or '2459' in val:
                        print(f"MATCH: {oid} = {val}")
                        
                    with open('snmp_dump.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{oid} = {val}\n")
    except Exception as e:
        print(f"Exception: {e}")
            
    print(f"Walked {count} OIDs.")

asyncio.run(walk_hp())
