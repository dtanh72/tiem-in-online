"""
PRINT SHOP - LOCAL SNMP SCANNER AGENT
--------------------------------------
Phiên bản: 1.0 (Hybrid CORS Mode)
Mô tả: File này cần được để bật trên Máy tính cửa hàng (nằm trong mạng LAN chứa máy in).
Nó sẽ tạo một API cục bộ (cổng 23456) kết nối liền mạch với chức năng Scanner trên Web (Vercel).
Các IP được lấy từ Web sẽ gửi trực tiếp đến script này qua cổng nội bộ, script này cào số và trả thẳng về Web để hiện thanh tiến độ rất đẹp.
"""

import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from pysnmp.hlapi.asyncio import *

app = Flask(__name__)
PORT = 23456
# Bật CORS cho phép Web (Ví dụ Vercel/Localhost) gửi Request nặc danh vào Local
CORS(app)

async def fetch_counter(ip, community='public'):
    """ Hàm quăng gói tin SNMP đến từng IP cụ thể """
    snmp_engine = SnmpEngine()
    
    # 1) OID chuẩn thông thường (Printers phổ thông)
    target_oid = ObjectIdentity('1.3.6.1.2.1.43.10.2.1.4.1.1')
    
    # 2) OID dự phòng cho HP Designjet (in mét vuông/inch)
    target_oid_hp = ObjectIdentity('1.3.6.1.4.1.11.2.3.9.4.2.1.4.1.12.2.5.1.0')

    try:
        errIndication, errStatus, errIndex, varBinds = await getCmd(
            snmp_engine,
            CommunityData(community, mpModel=0),
            UdpTransportTarget((ip, 161), timeout=1, retries=1),
            ContextData(),
            ObjectType(target_oid)
        )
    except Exception as e:
        return f"Err: {e}", None

    val = None
    status_str = None

    if errIndication or errStatus:
        errInd1 = errIndication
        errStat1 = errStatus

        # Fallback thử OID HP DesignJet
        try:
            errInd2, errStat2, errIdx2, varBinds2 = await getCmd(
                snmp_engine,
                CommunityData(community, mpModel=0),
                UdpTransportTarget((ip, 161), timeout=1, retries=0),
                ContextData(),
                ObjectType(target_oid_hp)
            )
            
            if not errInd2 and not errStat2:
                # hp metric in square inches -> m2
                v = int(varBinds2[0][1])
                if v > 0:
                    val = int(round(v / 1550.0031))
                    status_str = "OK"
        except:
            pass

        if status_str is None:
            status_str = str(errInd1) if errInd1 else str(errStat1)
            
        return status_str, val
    else:
        try:
            v = int(varBinds[0][1])
            return "OK", v
        except Exception:
            # Fallback nếu máy in OID tiêu chuẩn nhưng ko trả int hợp lệ (xảy ra với form lạ của HP)
            try:
                eI, eS, eId, varBinds3 = await getCmd(
                    snmp_engine,
                    CommunityData(community, mpModel=0),
                    UdpTransportTarget((ip, 161), timeout=1, retries=0),
                    ContextData(),
                    ObjectType(target_oid_hp)
                )
                if not eI and not eS:
                    v = int(varBinds3[0][1])
                    if v > 0:
                        val = int(round(v / 1550.0031))
                        status_str = "OK"
            except:
                pass
                
        if status_str is None:
            status_str = str(errIndication) if errIndication else str(errStatus)
            
        return status_str, val

async def fetch_all(ips_list, comm):
    tasks = [fetch_counter(ip, comm) for ip in ips_list]
    return await asyncio.gather(*tasks, return_exceptions=True)

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """ 
    Nhận Payload JSON từ trình duyệt Web (hoặc Postman)
    Body: {"ips": ["192.168.1.1", "192.168.1.2"], "community": "public"}
    """
    data = request.json or {}
    ips = data.get('ips', [])
    community = data.get('community', 'public')

    if not ips:
        return jsonify({'success': False, 'error': 'Vui lòng cung cấp danh sách mảng IP (ips)'}), 400

    results = []
    
    # Run Async SNMP Scan Batch
    raw_results = asyncio.run(fetch_all(ips, community))

    for i, ip in enumerate(ips):
        res = raw_results[i]
        if isinstance(res, Exception):
             results.append({'ip': ip, 'status': f'Exception: {res}', 'counter': None})
        else:
            status, counter = res
            results.append({'ip': ip, 'status': status, 'counter': counter if status == "OK" else None})

    return jsonify({'success': True, 'results': results})

@app.route('/')
def home():
    return f"""
    <h2>Print Shop Local Agent đang hoạt động!</h2>
    <p>Trạm quét nằm trong mạng LAN đã nối mạch thành công.</p>
    <p>Cổng giao tiếp Local: {PORT}</p>
    """

if __name__ == '__main__':
    print(f"===========================================================")
    print(f"BẮT ĐẦU CHẠY LOCAL AGENT (HỖ TRỢ QUÉT SNMP MÁY IN LOCAL)")
    print(f"===========================================================")
    print(f"Thu nhỏ cửa sổ này xuống thanh Taskbar và mở Web Print Shop của anh lên!")
    print(f"Listening on http://0.0.0.0:{PORT}...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
