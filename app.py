from flask import Flask, render_template, request, jsonify, send_file
import requests
import qrcode
import os
import qrcode.image.svg 
import io  

app = Flask(__name__)

# Ensure directories exist
os.makedirs(os.path.join('static', 'qrcodes'), exist_ok=True)
os.makedirs(os.path.join('static', 'uploads'), exist_ok=True) 

# ☁️ SUPABASE CLOUD REST API SETUP ☁️
SUPABASE_URL = "https://yxzsrdenjpecyyenwnxf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4enNyZGVuanBlY3l5ZW53bnhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMzMjM2MjMsImV4cCI6MjA4ODg5OTYyM30.7S3A3iJmUrH3JCrf23v-hmQbRAxe-3a7-48CgWiGke4"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/pro')
def pro_dashboard():
    return render_template('tourpro-dashboard.html')

def upload_to_supabase(file_bytes, file_name, content_type):
    url = f"{SUPABASE_URL}/storage/v1/object/yatra_assets/{file_name}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true"  
    }
    res = requests.post(url, headers=headers, data=file_bytes)
    
    if res.status_code in [200, 201]:
        return f"{SUPABASE_URL}/storage/v1/object/public/yatra_assets/{file_name}"
    else:
        print("Supabase Upload Error:", res.text)
        return None

@app.route('/api/add_passenger', methods=['POST'])
def add_passenger():
    p_id = request.form.get('id') 
    pnr = request.form.get('pnr')
    city = request.form.get('city')

    if not pnr:
        return jsonify({"error": "PNR is required"}), 400

    base_url = request.host_url 
    qr_data = f"{base_url}p/{pnr}" 
    
    qr_img = qrcode.make(qr_data)
    img_io = io.BytesIO()
    qr_img.save(img_io, 'PNG')
    img_bytes = img_io.getvalue()
    qr_png_url = upload_to_supabase(img_bytes, f"qrcodes/qr_{pnr}.png", "image/png")

    factory = qrcode.image.svg.SvgImage
    qr_svg_img = qrcode.make(qr_data, image_factory=factory)
    svg_io = io.BytesIO()
    qr_svg_img.save(svg_io)
    svg_bytes = svg_io.getvalue()
    qr_svg_url = upload_to_supabase(svg_bytes, f"qrcodes/qr_{pnr}.svg", "image/svg+xml")

    photo_path = None
    aadhaar_path = None

    if 'photo' in request.files:
        photo_file = request.files['photo']
        if photo_file.filename != '':
            ext = photo_file.filename.split('.')[-1]
            p_filename = f"photos/photo_{pnr}.{ext}"
            photo_path = upload_to_supabase(photo_file.read(), p_filename, photo_file.content_type)

    if 'aadhaar' in request.files:
        aadhaar_file = request.files['aadhaar']
        if aadhaar_file.filename != '':
            ext = aadhaar_file.filename.split('.')[-1]
            a_filename = f"aadhaar/aadhaar_{pnr}.{ext}"
            aadhaar_path = upload_to_supabase(aadhaar_file.read(), a_filename, aadhaar_file.content_type)

    try:
        passenger_data = {
            "name": request.form.get('name'),
            "age": int(request.form.get('age')) if request.form.get('age') else 0,
            "blood_group": request.form.get('blood'),
            "group_name": request.form.get('group'), 
            "contact": request.form.get('contact'),
            "pnr": pnr,
            "medical": request.form.get('medical'),
            "city": request.form.get('city')
        }

        if qr_png_url:
            passenger_data["qr_path"] = qr_png_url
        if photo_path:
            passenger_data["photo_path"] = photo_path
        if aadhaar_path:
            passenger_data["aadhaar_path"] = aadhaar_path
        
        if p_id and p_id != 'null':
            update_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}"
            response = requests.patch(update_url, headers=HEADERS, json=passenger_data)
            success_msg = f"{request.form.get('name')}'s profile updated successfully! ☁️"
        else:
            passenger_data["attendance_logs"] = {"General Boarding": "pending"}
            insert_url = f"{SUPABASE_URL}/rest/v1/passengers"
            response = requests.post(insert_url, headers=HEADERS, json=passenger_data)
            success_msg = f"{request.form.get('name')} safely saved to Cloud! ☁️"
        
        if response.status_code in [200, 201, 204]:
            return jsonify({
                "message": success_msg, 
                "qr_url": qr_png_url, 
                "qr_svg_url": qr_svg_url 
            })
        else:
            return jsonify({"error": "Failed to save to cloud"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_passengers', methods=['GET'])
def get_passengers():
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?select=*&order=id.desc"
        response = requests.get(fetch_url, headers=HEADERS)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to fetch from cloud"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/p/<pnr>')
def passenger_profile(pnr):
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?pnr=eq.{pnr}&select=*"
        response = requests.get(fetch_url, headers=HEADERS)
        
        if response.status_code == 200 and len(response.json()) > 0:
            passenger = response.json()[0]
            group_name = passenger.get('group_name')
            
            admin_phone = ""
            if group_name:
                contact_url = f"{SUPABASE_URL}/rest/v1/group_contacts?group_letter=eq.{group_name}&select=phone"
                contact_res = requests.get(contact_url, headers=HEADERS)
                if contact_res.status_code == 200 and len(contact_res.json()) > 0:
                    admin_phone = contact_res.json()[0].get('phone', '')

            return render_template('sos.html', p=passenger, admin_phone=admin_phone)
        else:
            return "❌ YatraShield: PNR Not Found or Invalid QR Code", 404
            
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/update_status', methods=['POST'])
def update_status():
    data = request.json
    p_id = data.get('id')
    event_name = data.get('event_name') 
    new_status = data.get('status') 
    
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}&select=attendance_logs"
        res = requests.get(fetch_url, headers=HEADERS)
        
        if res.status_code == 200 and len(res.json()) > 0:
            current_logs = res.json()[0].get('attendance_logs')
            if current_logs is None:
                current_logs = {}
            
            current_logs[event_name] = new_status 
            
            update_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}"
            patch_res = requests.patch(update_url, headers=HEADERS, json={"attendance_logs": current_logs})
            
            if patch_res.status_code in [200, 204]:
                return jsonify({"message": f"Status Updated for {event_name}!"})
            else:
                return jsonify({"error": "Failed to update cloud"}), 500
        else:
            return jsonify({"error": "Passenger not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/save_group_contacts', methods=['POST'])
def save_group_contacts():
    contacts = request.json
    try:
        del_url = f"{SUPABASE_URL}/rest/v1/group_contacts?group_letter=not.is.null"
        requests.delete(del_url, headers=HEADERS)

        data_to_insert = [{"group_letter": k, "phone": v} for k, v in contacts.items() if str(v).strip()]
        
        if data_to_insert:
            insert_url = f"{SUPABASE_URL}/rest/v1/group_contacts"
            requests.post(insert_url, headers=HEADERS, json=data_to_insert)

        return jsonify({"message": "Contacts saved securely to Cloud!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_group_contacts', methods=['GET'])
def get_group_contacts():
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/group_contacts?select=*"
        res = requests.get(fetch_url, headers=HEADERS)
        if res.status_code == 200:
            contacts_dict = {item['group_letter']: item['phone'] for item in res.json()}
            return jsonify(contacts_dict)
        return jsonify({})
    except Exception as e:
        return jsonify({}), 500

@app.route('/api/delete_passenger', methods=['POST'])
def delete_passenger():
    data = request.json
    p_id = data.get('id')
    try:
        del_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}"
        response = requests.delete(del_url, headers=HEADERS)
        if response.status_code in [200, 204]:
            return jsonify({"message": "Passenger deleted successfully"})
        else:
            return jsonify({"error": "Failed to delete"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download_qr/<file_type>/<pnr>')
def download_qr_proxy(file_type, pnr):
    try:
        ext = 'png' if file_type.lower() == 'png' else 'svg'
        content_type = 'image/png' if ext == 'png' else 'image/svg+xml'
        file_name = f"qr_{pnr}.{ext}"
        
        supabase_public_url = f"{SUPABASE_URL}/storage/v1/object/public/yatra_assets/qrcodes/{file_name}"
        response = requests.get(supabase_public_url)
        
        if response.status_code == 200:
            return send_file(
                io.BytesIO(response.content),
                mimetype=content_type,
                as_attachment=True,
                download_name=f"YatraShield_QR_{pnr}.{ext}"
            )
        return "File not found", 404
    except Exception as e:
        return str(e), 500

# ==========================================
# 🔥 PRO ADMIN SAAS ROUTES (SEPARATE DATA) 🔥
# ==========================================

@app.route('/api/pro_get_passengers', methods=['GET'])
def pro_get_passengers():
    try:
        fetch_url = f"{SUPABASE_URL}/rest/v1/pro_passengers?select=*&order=id.desc"
        response = requests.get(fetch_url, headers=HEADERS)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({"error": "Failed to fetch from cloud"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pro_add_passenger', methods=['POST'])
def pro_add_passenger():
    try:
        data = request.json
        new_passenger = {
            "name": data.get("name"),
            "phone": data.get("phone"),
            "tour_group": data.get("group"),
            "total_fare": data.get("total", 0),
            "amount_paid": data.get("paid", 0)
        }
        insert_url = f"{SUPABASE_URL}/rest/v1/pro_passengers"
        response = requests.post(insert_url, headers=HEADERS, json=new_passenger)
        if response.status_code in [200, 201]:
            return jsonify({"message": "Pro Passenger Added!"}), 200
        else:
            return jsonify({"error": "Failed to save to cloud"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# FILE KE EKDUM AAKHIR MEIN YEHI HONA CHAHIYE
# ==========================================
@app.route('/api/pro_delete_passenger', methods=['POST'])
def pro_delete_passenger():
    data = request.json
    p_id = data.get('id')
    try:
        del_url = f"{SUPABASE_URL}/rest/v1/pro_passengers?id=eq.{p_id}"
        response = requests.delete(del_url, headers=HEADERS)
        if response.status_code in [200, 204]:
            return jsonify({"message": "Deleted successfully"})
        return jsonify({"error": "Failed to delete"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/pro_update_payment', methods=['POST'])
def pro_update_payment():
    data = request.json
    p_id = data.get('id')
    new_paid = data.get('paid')
    try:
        update_url = f"{SUPABASE_URL}/rest/v1/pro_passengers?id=eq.{p_id}"
        response = requests.patch(update_url, headers=HEADERS, json={"amount_paid": new_paid})
        if response.status_code in [200, 204]:
            return jsonify({"message": "Payment updated"}), 200
        return jsonify({"error": "Failed to update"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # ==========================================
# 🔥 ADMIN LOGIN VERIFICATION
# ==========================================
@app.route('/api/pro_admin_login', methods=['POST'])
def pro_admin_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    try:
        # Supabase se email dhoondho
        fetch_url = f"{SUPABASE_URL}/rest/v1/admin_users?email=eq.{email}&select=*"
        response = requests.get(fetch_url, headers=HEADERS)
        
        if response.status_code == 200:
            users = response.json()
            if len(users) > 0:
                # Email mil gaya, ab password match karo
                db_password = users[0].get('password')
                if password == db_password:
                    return jsonify({"message": "Login successful"}), 200
                else:
                    return jsonify({"error": "Invalid password"}), 401
            else:
                return jsonify({"error": "User not found"}), 404
        else:
            return jsonify({"error": "Database error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
   # ==========================================
# 🖨️ PRINT VIP ID CARD ROUTE (With Admin Phone)
# ==========================================
@app.route('/id_card/<int:p_id>', methods=['GET'])
def print_id_card(p_id):
    try:
        # 1. Passenger ka data laao
        fetch_url = f"{SUPABASE_URL}/rest/v1/passengers?id=eq.{p_id}&select=*"
        res = requests.get(fetch_url, headers=HEADERS)
        
        if res.status_code == 200 and len(res.json()) > 0:
            p_data = res.json()[0]
            
            # 2. Passenger ke Group se Admin ka Number nikaalo
            group_name = p_data.get('group_name')
            admin_phone = ""
            if group_name:
                # group_contacts table check karo
                contact_url = f"{SUPABASE_URL}/rest/v1/group_contacts?group_letter=eq.{group_name}&select=phone"
                c_res = requests.get(contact_url, headers=HEADERS)
                if c_res.status_code == 200 and len(c_res.json()) > 0:
                    admin_phone = c_res.json()[0].get('phone', '')
            
            # 3. Admin phone ko data me jod do aur HTML ko bhej do
            p_data['admin_phone'] = admin_phone
            
            return render_template('id_card.html', p=p_data)
            
        return "Passenger data not found!", 404
    except Exception as e:
        return str(e), 500
if __name__ == '__main__':
    app.run(debug=True)