from app import app
import traceback

app.config['WTF_CSRF_ENABLED'] = False
with app.test_client() as c:
    try:
        r = c.post('/tools/api/scan-printers', data={'ip_list': '192.168.1.37', 'community': 'public'})
        print(r.status_code)
        print(r.data.decode()[:500])
    except Exception as e:
        traceback.print_exc()
