import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

async def run():
    iterator = get_cmd(
        SnmpEngine(),
        CommunityData('public', mpModel=0),
        UdpTransportTarget(('8.8.8.8', 161), timeout=1.0, retries=0),
        ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'))
    )
    try:
        errorIndication, errorStatus, errorIndex, varBinds = await iterator
        print(errorIndication, errorStatus, varBinds)
    except Exception as e:
        print("Exception", e)

asyncio.run(run())
