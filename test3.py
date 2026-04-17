import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

async def scan():
    tran = await UdpTransportTarget.create(('192.168.1.150', 161))
    iterator = get_cmd(
        SnmpEngine(),
        CommunityData('public', mpModel=0),
        tran,
        ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.2.1.43.10.2.1.4.1.1'))
    )
    result = await iterator
    print(result)

asyncio.run(scan())
