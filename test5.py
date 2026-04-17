import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

async def scan():
    tran = await UdpTransportTarget.create(('192.168.1.37', 161), timeout=1.0, retries=0)
    iterator = get_cmd(
        SnmpEngine(),
        CommunityData('public', mpModel=0),
        tran,
        ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.2.1.43.10.2.1.4.1.1')),
        ObjectType(ObjectIdentity('1.3.6.1.4.1.11.2.3.9.4.2.1.4.1.2.6.0'))
    )
    errorIndication, errorStatus, errorIndex, varBinds = await iterator
    print("errorIndication:", errorIndication)
    print("errorStatus:", errorStatus)
    print("errorIndex:", errorIndex)
    print("varBinds:", varBinds)

asyncio.run(scan())
